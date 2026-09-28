# Trace asset schema

Use the following normalized execution-context record shape for downstream work:

```json
{
  "id": "org.apache.dubbo.common.url.URLParamTest",
  "repo_name": "dubbo",
  "repo": "dubbo",
  "trace_id": "org.apache.dubbo.common.url.URLParamTest",
  "test_name": "org.apache.dubbo.common.url.URLParamTest",
  "official_test_path": "dubbo-common/src/test/java/org/apache/dubbo/common/url/URLParamTest.java",
  "official_test_class": "org.apache.dubbo.common.url.URLParamTest",
  "replay_cmd": ["./mvnw", "-q", "-pl", "dubbo-common", "-Dtest=org.apache.dubbo.common.url.URLParamTest", "test"],
  "methods": [
    {"kind": "test", "name": "...", "path": "..."},
    {"kind": "prod", "name": "...", "path": "..."}
  ],
  "cmd": ["./mvnw", "-q", "-pl", "dubbo-common", "-Dtest=org.apache.dubbo.common.url.URLParamTest", "test"],
  "distinct_prod_function_count": 12,
  "trace_bucket": "short",
  "trace_summary": "Short normalized summary for agent prompting.",
  "anchors": [
    {
      "file": "dubbo-common/src/main/java/...",
      "symbol": "URLParam.getMethodParameter",
      "role": "guarded lookup branch"
    }
  ],
  "bug_related_files": [
    "dubbo-common/src/main/java/org/apache/dubbo/common/url/component/URLParam.java"
  ]
}
```

Use a separate command bundle only if you need to decouple the replay command from the trace record.

The core inject loader accepts either `id` or `trace_id`; include both so older wrappers and
new reviewer scripts resolve the same record. The command bundle should use the same key:

```json
{
  "commands": [
    {
      "id": "org.apache.dubbo.common.url.URLParamTest",
      "test_name": "org.apache.dubbo.common.url.URLParamTest",
      "cmd": ["./mvnw", "-q", "-pl", "dubbo-common", "-Dtest=org.apache.dubbo.common.url.URLParamTest", "test"],
      "repo": "dubbo",
      "build": "maven"
    }
  ]
}
```

For release packaging, keep the per-case `execution_context.json` sidecar with the same
`trace_id`, `trace_bucket`, `trace_summary`, `methods`, `anchors`, and `bug_related_files`.
