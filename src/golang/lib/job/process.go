package job

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"sync"
	"time"

	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/dropbox/godropbox/errors"
	"github.com/go-co-op/gocron"
	"github.com/google/uuid"
	"github.com/shirou/gopsutil/process"
	log "github.com/sirupsen/logrus"
)

const (
	defaultPythonExecutorPackage = "aqueduct_executor"
	connectorPythonPath          = "operators.connectors.tabular.main"
	paramPythonPath              = "operators.param_executor.main"
	systemMetricPythonPath       = "operators.system_metric_executor.main"
	executorBinary               = "executor"
	functionExecutorBashScript   = "start-function-executor.sh"

	processRunningStatus = "R"

	BinaryDir          = "bin/"
	OperatorStorageDir = "storage/operators/"
	LogsDir            = "logs/"
)

var (
	defaultBinaryDir          = path.Join(os.Getenv("HOME"), ".aqueduct", BinaryDir)
	defaultOperatorStorageDir = path.Join(os.Getenv("HOME"), ".aqueduct", OperatorStorageDir)
	defaultLogsDir            = path.Join(os.Getenv("HOME"), ".aqueduct", "server", LogsDir)
)

type Command struct {
	cmd    *exec.Cmd
	stdout *bytes.Buffer
	stderr *bytes.Buffer
}

type cronMetadata struct {
	// If the cronJob is nil, it means the corresponding workflow has been paused.
	cronJob *gocron.Job
	// We need to store the job spec because when the workflow is resumed from the pause state, we
	// need the spec to redeploy the cron job.
	jobSpec Spec
}

// Please use thread-safe read / insert / remove APIs to maintain maps.
// These APIs are wrapped with proper locks to support concurrency.
// Never try to access map using go's native APIs.
type ProcessJobManager struct {
	conf          *ProcessConfig
	cmds          map[string]*Command
	cronScheduler *gocron.Scheduler
	// A mapping from cron job name to cron job object pointer.
	cronMapping map[string]*cronMetadata
	cmdMutex    *sync.RWMutex
	cronMutex   *sync.RWMutex
}

func (j *ProcessJobManager) getCmd(key string) (*Command, bool) {
	j.cmdMutex.RLock()
	cmd, ok := j.cmds[key]
	j.cmdMutex.RUnlock()
	return cmd, ok
}

func (j *ProcessJobManager) setCmd(key string, cmd *Command) {
	j.cmdMutex.Lock()
	j.cmds[key] = cmd
	j.cmdMutex.Unlock()
}

func (j *ProcessJobManager) deleteCmd(key string) {
	j.cmdMutex.Lock()
	delete(j.cmds, key)
	j.cmdMutex.Unlock()
}

func (j *ProcessJobManager) getCronMap(key string) (*cronMetadata, bool) {
	j.cronMutex.RLock()
	cron, ok := j.cronMapping[key]
	j.cronMutex.RUnlock()
	return cron, ok
}

func (j *ProcessJobManager) setCronMap(key string, cron *cronMetadata) {
	j.cronMutex.Lock()
	j.cronMapping[key] = cron
	j.cronMutex.Unlock()
}

func (j *ProcessJobManager) deleteCronMap(key string) {
	j.cronMutex.Lock()
	delete(j.cronMapping, key)
	j.cronMutex.Unlock()
}

func NewProcessJobManager(conf *ProcessConfig) (*ProcessJobManager, error) {
	if conf.PythonExecutorPackage == "" {
		conf.PythonExecutorPackage = defaultPythonExecutorPackage
	}

	if conf.BinaryDir == "" {
		conf.BinaryDir = defaultBinaryDir
	}

	if conf.OperatorStorageDir == "" {
		conf.OperatorStorageDir = defaultOperatorStorageDir
	}

	cronScheduler := gocron.NewScheduler(time.UTC)
	cronScheduler.StartAsync()

	return &ProcessJobManager{
		conf:          conf,
		cmds:          map[string]*Command{},
		cronScheduler: cronScheduler,
		cronMapping:   map[string]*cronMetadata{},
		cmdMutex:      &sync.RWMutex{},
		cronMutex:     &sync.RWMutex{},
	}, nil
}

func (j *ProcessJobManager) mapJobTypeToCmd(jobName string, spec Spec) (*exec.Cmd, error) {
	var cmd *exec.Cmd
	if spec.Type() == WorkflowJobType {
		workflowSpec, ok := spec.(*WorkflowSpec)
		if !ok {
			return nil, errors.New("Unable to cast job spec to WorkflowSpec.")
		}

		specStr, err := EncodeSpec(workflowSpec, GobSerializationType)
		if err != nil {
			return nil, err
		}

		logFilePath := path.Join(defaultLogsDir, jobName)
		log.Infof("Logs for job %s are stored in %s", jobName, logFilePath)

		cmd = exec.Command(
			fmt.Sprintf("%s/%s", j.conf.BinaryDir, executorBinary),
			"--spec",
			specStr,
			"--logs-path",
			logFilePath,
		)
	} else if spec.Type() == WorkflowRetentionType {
		workflowRetentionSpec, ok := spec.(*WorkflowRetentionSpec)
		if !ok {
			return nil, errors.New("Unable to cast job spec to workflowRetentionSpec.")
		}

		specStr, err := EncodeSpec(workflowRetentionSpec, GobSerializationType)
		if err != nil {
			return nil, err
		}

		logFilePath := path.Join(defaultLogsDir, jobName)
		log.Infof("Logs for job %s are stored in %s", jobName, logFilePath)

		cmd = exec.Command(
			fmt.Sprintf("%s/%s", j.conf.BinaryDir, executorBinary),
			"--spec",
			specStr,
			"--logs-path",
			logFilePath,
		)
	} else if spec.Type() == FunctionJobType {
		functionSpec, ok := spec.(*FunctionSpec)
		if !ok {
			return nil, ErrInvalidJobSpec
		}

		functionSpec.FunctionExtractPath = path.Join(j.conf.OperatorStorageDir, uuid.New().String())
		specStr, err := EncodeSpec(spec, JsonSerializationType)
		if err != nil {
			return nil, err
		}

		cmd = exec.Command(
			"bash",
			filepath.Join(j.conf.BinaryDir, functionExecutorBashScript),
			specStr,
		)
	} else if spec.Type() == ParamJobType {
		specStr, err := EncodeSpec(spec, JsonSerializationType)
		if err != nil {
			return nil, err
		}

		cmd = exec.Command(
			"python3",
			"-m",
			fmt.Sprintf("%s.%s", j.conf.PythonExecutorPackage, paramPythonPath),
			"--spec",
			specStr,
		)
	} else if spec.Type() == AuthenticateJobType ||
		spec.Type() == LoadJobType ||
		spec.Type() == ExtractJobType ||
		spec.Type() == LoadTableJobType ||
		spec.Type() == DeleteSavedObjectsJobType ||
		spec.Type() == DiscoverJobType {
		specStr, err := EncodeSpec(spec, JsonSerializationType)
		if err != nil {
			return nil, err
		}

		cmd = exec.Command(
			"python3",
			"-m",
			fmt.Sprintf("%s.%s", j.conf.PythonExecutorPackage, connectorPythonPath),
			"--spec",
			specStr,
		)
	} else if spec.Type() == SystemMetricJobType {
		specStr, err := EncodeSpec(spec, JsonSerializationType)
		if err != nil {
			return nil, err
		}

		return exec.Command(
			"python3",
			"-m",
			fmt.Sprintf("%s.%s", j.conf.PythonExecutorPackage, systemMetricPythonPath),
			"--spec",
			specStr,
		), nil
	} else {
		return nil, errors.New("Unsupported JobType was passed in.")
	}
	log.Infof("Running job with command: %s", cmd.String())
	return cmd, nil
}

func (j *ProcessJobManager) generateCronFunction(name string, jobSpec Spec) func() {
	return func() {
		jobName := fmt.Sprintf("%s-%d", name, time.Now().Unix())
		err := j.Launch(context.Background(), jobName, jobSpec)
		if err != nil {
			log.Errorf("Error running cron job %s: %v", jobName, err)
		} else {
			log.Infof("Launched cron job %s", jobName)
		}
	}
}

func (j *ProcessJobManager) Config() Config {
	return j.conf
}

func (j *ProcessJobManager) Launch(
	ctx context.Context,
	name string,
	spec Spec,
) error {
	log.Infof("Running %s job %s.", spec.Type(), name)
	if _, ok := j.getCmd(name); ok {
		return ErrJobAlreadyExists
	}

	cmd, err := j.mapJobTypeToCmd(name, spec)
	if err != nil {
		return err
	}
	cmd.Env = os.Environ()

	stdout := &bytes.Buffer{}
	stderr := &bytes.Buffer{}
	j.setCmd(name, &Command{
		cmd:    cmd,
		stdout: stdout,
		stderr: stderr,
	})
	cmd.Stdout = stdout
	cmd.Stderr = stderr

	return cmd.Start()
}

func (j *ProcessJobManager) Poll(ctx context.Context, name string) (shared.ExecutionStatus, error) {
	command, ok := j.getCmd(name)
	if !ok {
		return shared.UnknownExecutionStatus, ErrJobNotExist
	}

	proc, err := process.NewProcess(int32(command.cmd.Process.Pid))
	if err != nil {
		return shared.UnknownExecutionStatus, err
	}

	status, err := proc.Status()
	if err != nil {
		return shared.UnknownExecutionStatus, err
	}

	if status == processRunningStatus {
		return shared.RunningExecutionStatus, nil
	}

	// TODO(ENG-1195): function operators that fail have their exceptions caught, and so return success
	//  execution status when it should be failure.
	// TODO(ENG-1196): workflows that do not completely succeed still return a success execution status here.
	err = command.cmd.Wait()
	// After wait, we are done with this job and already consumed all of its output, so we garbage
	// collect the entry in j.cmds.
	defer j.deleteCmd(name)
	if err != nil {
		log.Errorf("Unexpected error occurred while executing job %s: %v. Stdout: \n %s \n Stderr: \n %s",
			name,
			err,
			command.stdout.String(),
			command.stderr.String(),
		)
		return shared.FailedExecutionStatus, nil // nolint:nilerr // Poll() should not error on command execution issues.
	}

	log.Infof("Job %s Stdout:\n %s \n Stderr: \n %s",
		name,
		command.stdout.String(),
		command.stderr.String(),
	)
	return shared.SucceededExecutionStatus, nil
}

func (j *ProcessJobManager) DeployCronJob(
	ctx context.Context,
	name string,
	period string,
	spec Spec,
) error {
	if _, ok := j.getCronMap(name); ok {
		return errors.Newf("Cron job with name %s already exists", name)
	}

	cron := &cronMetadata{
		cronJob: nil,
		jobSpec: spec,
	}

	j.setCronMap(name, cron)

	if period != "" {
		cronJob, err := j.cronScheduler.Cron(period).Do(j.generateCronFunction(name, spec))
		if err != nil {
			return err
		}

		cron.cronJob = cronJob
	}

	return nil
}

func (j *ProcessJobManager) CronJobExists(ctx context.Context, name string) bool {
	_, ok := j.getCronMap(name)
	return ok
}

func (j *ProcessJobManager) EditCronJob(ctx context.Context, name string, cronString string) error {
	cronMetadata, ok := j.getCronMap(name)
	if !ok {
		return errors.New("Cron job not found")
	} else {
		if cronMetadata.cronJob == nil {
			// This means the current cron job is paused.
			if cronString == "" {
				return errors.Newf("Attempting to pause an already paused cron job %s", name)
			}

			cronJob, err := j.cronScheduler.Cron(cronString).Do(j.generateCronFunction(name, cronMetadata.jobSpec))
			if err != nil {
				return err
			}

			cronMetadata.cronJob = cronJob
		} else {
			if cronString == "" {
				// This means we want to pause the cron job.
				j.cronScheduler.RemoveByReference(cronMetadata.cronJob)
				cronMetadata.cronJob = nil
			} else {
				_, err := j.cronScheduler.Job(cronMetadata.cronJob).Cron(cronString).Update()
				if err != nil {
					return err
				}
			}
		}
		return nil
	}
}

func (j *ProcessJobManager) DeleteCronJob(ctx context.Context, name string) error {
	cronMetadata, ok := j.getCronMap(name)
	if ok {
		j.cronScheduler.RemoveByReference(cronMetadata.cronJob)
		j.deleteCronMap(name)
	}

	return nil
}
