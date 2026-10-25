{{- define "detector.labels" -}}
app.kubernetes.io/name: detector
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: minieyes
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
minieyes.io/site: {{ .Values.site }}
{{- end }}

{{- define "detector.selector" -}}
app.kubernetes.io/name: detector
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
