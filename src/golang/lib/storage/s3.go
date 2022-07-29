package storage

import (
	"bytes"
	"context"
	"net/url"
	"path"

	"github.com/aqueducthq/aqueduct/lib/collections/shared"
	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/awserr"
	"github.com/aws/aws-sdk-go/aws/credentials"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/aws/aws-sdk-go/service/s3/s3manager"
)

type s3Storage struct {
	s3Config *shared.S3Config
}

func newS3Storage(s3Config *shared.S3Config) *s3Storage {
	return &s3Storage{
		s3Config: s3Config,
	}
}

// parseBucketAndKey takes the bucket in the form of s3://bucket/path
// and a key and parses the bucket name and the key.
func (s *s3Storage) parseBucketAndKey(key string) (string, string, error) {
	u, err := url.Parse(s.s3Config.Bucket)
	if err != nil {
		return "", "", err
	}

	bucket := u.Host
	key = path.Join(u.Path, key)

	return bucket, key, nil
}

func (s *s3Storage) Get(ctx context.Context, key string) ([]byte, error) {
	sess, err := CreateS3Session(s.s3Config)
	if err != nil {
		return nil, err
	}

	buff := &aws.WriteAtBuffer{}
	downloader := s3manager.NewDownloader(sess)

	bucket, key, err := s.parseBucketAndKey(key)
	if err != nil {
		return nil, err
	}

	_, err = downloader.DownloadWithContext(
		ctx,
		buff,
		&s3.GetObjectInput{
			Bucket: aws.String(bucket),
			Key:    aws.String(key),
		})
	if err != nil {
		// Cast `err` to an AWS error to check code
		if aerr, ok := err.(awserr.Error); ok {
			if aerr.Code() == s3.ErrCodeNoSuchKey {
				return nil, ErrObjectDoesNotExist
			}
		}

		return nil, err
	}
	return buff.Bytes(), nil
}

func (s *s3Storage) Put(ctx context.Context, key string, value []byte) error {
	sess, err := CreateS3Session(s.s3Config)
	if err != nil {
		return err
	}

	file := bytes.NewReader(value)

	uploader := s3manager.NewUploader(sess)

	bucket, key, err := s.parseBucketAndKey(key)
	if err != nil {
		return err
	}

	_, err = uploader.UploadWithContext(
		ctx,
		&s3manager.UploadInput{
			Bucket: aws.String(bucket),
			Key:    aws.String(key),
			Body:   file,
		})
	if err != nil {
		return err
	}
	return nil
}

func (s *s3Storage) Delete(ctx context.Context, key string) error {
	sess, err := CreateS3Session(s.s3Config)
	if err != nil {
		return err
	}

	s3Client := s3.New(sess)

	bucket, key, err := s.parseBucketAndKey(key)
	if err != nil {
		return err
	}

	_, err = s3Client.DeleteObjectWithContext(
		ctx,
		&s3.DeleteObjectInput{
			Bucket: aws.String(bucket),
			Key:    aws.String(key),
		},
	)
	return err
}

func CreateS3Session(s3Config *shared.S3Config) (*session.Session, error) {
	sess, err := session.NewSession(&aws.Config{
		Region: aws.String(s3Config.Region),
		Credentials: credentials.NewSharedCredentials(
			s3Config.CredentialsPath,
			s3Config.CredentialsProfile,
		),
	})
	if err != nil {
		return nil, err
	}
	return sess, nil
}
