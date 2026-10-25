{{- define "event-api.labels" -}}
app.kubernetes.io/name: event-api
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: minieyes
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
{{- end }}

{{- define "event-api.selector" -}}
app.kubernetes.io/name: event-api
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- /* Pod and container hardening shared by the API and the migration Job. */ -}}
{{- define "event-api.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{- define "event-api.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: [ALL]
{{- end }}

{{- define "event-api.databaseEnv" -}}
- name: MINIEYES_DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretName }}
      key: database-url
{{- end }}
