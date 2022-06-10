package systemmetric

// The value of a system metric must be JSON serializable.
type SystemMetric struct {
	MetricName string `json:"metricname"`
}
