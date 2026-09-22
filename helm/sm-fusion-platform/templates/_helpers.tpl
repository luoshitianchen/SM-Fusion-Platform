{{/*
通用辅助模板：名称/全名/标签选择器
*/}}
{{- define "sm-fusion-platform.name" -}}
{{ default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "sm-fusion-platform.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end -}}
{{- end }}

{{- define "sm-fusion-platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{- define "sm-fusion-platform.commonLabels" -}}
app.kubernetes.io/name: {{ include "sm-fusion-platform.name" . }}
helm.sh/chart: {{ include "sm-fusion-platform.chart" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "sm-fusion-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "sm-fusion-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "sm-fusion-platform.serviceAccountName" -}}
{{ default (printf "%s-sa" (include "sm-fusion-platform.fullname" .)) .Values.serviceAccount.name }}
{{- end }}
