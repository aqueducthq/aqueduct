package logging

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"

	aq_context "github.com/aqueducthq/aqueduct/lib/context"
	log "github.com/sirupsen/logrus"
)

type Component string

const (
	ServerComponent Component = "Server"
)

// We register an obfuscation function to alter the header value before logging it
// the key is the header name whose value is the func to apply to the header value.
var HeaderObfuscationFunctionMap map[string](func([]string) ([]string, error)) = map[string](func([]string) ([]string, error)){
	"Integration-Config": ObscurePasswordFromIntegrationConfig,
}

func LogRoute(
	ctx context.Context,
	routeName string,
	r *http.Request,
	excludedHeaderFields map[string]bool,
	statusCode int,
	component Component,
	serviceName string,
	err error,
) {
	headers := make(map[string][]string, len(r.Header)-len(excludedHeaderFields))
	for k, v := range r.Header {
		if _, ok := excludedHeaderFields[k]; !ok {
			if obfuscateFunction, obfuscate := HeaderObfuscationFunctionMap[k]; obfuscate {
				headers[k], err = obfuscateFunction(v)
				if err != nil {
					log.Errorf("Unable to obfuscate header for: "+k+"%v", err)
					// Since this is a logging route, we drop headers we cant obfuscate
					continue
				}
			} else {
				headers[k] = v
			}
		}
	}

	status := "SUCCEEDED"
	var errMsg string
	if err != nil {
		status = "ERROR"
		errMsg = err.Error()
	}

	log.WithFields(log.Fields{
		"ServiceName":   serviceName,
		"URL":           r.URL,
		"Headers":       headers,
		"Status":        status,
		"Code":          statusCode,
		"Component":     component,
		"Route":         routeName,
		"UserId":        ctx.Value(aq_context.UserIdKey),
		"UserRequestId": ctx.Value(aq_context.UserRequestIdKey),
		"Error":         errMsg,
	}).Info()
}

func LogAsyncEvent(
	ctx context.Context,
	component Component,
	serviceName string,
	err error,
) {
	status := "SUCCEEDED"
	var errMsg string
	if err != nil {
		status = "ERROR"
		errMsg = err.Error()
	}

	log.WithFields(log.Fields{
		"ServiceName":   serviceName,
		"Status":        status,
		"Component":     component,
		"UserId":        ctx.Value(aq_context.UserIdKey),
		"UserRequestId": ctx.Value(aq_context.UserRequestIdKey),
		"Error":         errMsg,
	}).Info()
}

// Replaces the password in an integration config string into the equivalent * string.
func ObscurePasswordFromIntegrationConfig(integrationConfigHeader []string) ([]string, error) {
	integrationConfigString := integrationConfigHeader[0]
	integrationConfig := map[string]string{}
	err := json.Unmarshal([]byte(integrationConfigString), &integrationConfig)
	if err != nil {
		return nil, err
	}
	if _, exists := integrationConfig["password"]; !exists {
		return integrationConfigHeader, nil
	}

	passwordLength := len(integrationConfig["password"])
	integrationConfig["password"] = strings.Repeat("*", passwordLength)
	newIntegrationConfigString, err := json.Marshal(integrationConfig)
	if err != nil {
		return nil, err
	}

	return []string{string(newIntegrationConfigString)}, nil
}
