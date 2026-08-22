{{- define "sm-fusion-platform.fullname" -}}
{{- printf "%s-%s" .Release.Name "sm-fusion-platform" | trunc 63 | trimSuffix "-" -}}
{{- end -}}
