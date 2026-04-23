# Webserver Security

Arelle's built-in webserver (started via `--webserver`) is intended for **trusted callers only**. It has no authentication layer and exposes functionality (including plug-in loading and arbitrary filesystem reads) that is inherently dangerous when reachable by untrusted clients.

This page describes the security posture of the webserver so that operators can deploy it responsibly.

## Intended Use

The webserver is appropriate for:

- A local machine used by a single user.
- An internal network where every user with network access to the port is already trusted to run code on the host.
- Automation pipelines that invoke the REST API from trusted systems on the same host or network.

It is **not** appropriate for:

- The public internet, directly or behind a reverse proxy.
- Any network that includes users you would not otherwise grant shell level trust to.
- Multi-tenant environments where callers should be isolated from each other.

## No Authentication

None of the REST routes perform authentication or authorization checks.

## Filesystem Read Access

Validation and view endpoints accept arbitrary file paths via parameters such as `file`, `entrypointFile`, and `import`. The server will attempt to open those paths with its own privileges. Although Arelle will only parse the content as XBRL, failures and log output can leak information about filesystem layout, path existence, and potentially file contents, back to the caller.

When deploying the webserver:

- Run the process as a low privilege user.
- Do not co-locate the server with secrets on disk (credentials, private keys, other tenants data).
- Keep the listening port on a trusted interface (`localhost` or a restricted internal interface).

## Plug-in Loading

`/rest/configure` and `/rest/xbrl/...` accept a `plugins=` parameter that can load Python plug-ins into the running server. Loaded plug-ins execute with the server's privileges.

- **Local plug-in references are accepted.** An administrator on a trusted deployment can still configure plug-ins via the REST API using a module name, relative path, or absolute filesystem path — the same syntax supported by `--plugins` on the command line.
- **Remote URL plug-in references are rejected.** References beginning with a URL scheme (`http://`, `https://`, etc.) are refused with a `400 Bad Request`.

If you need to install a plug-in from a URL, do so out-of-band (by downloading the module to the plug-in directory) before starting the webserver, or use the command line `--plugins` option on a trusted invocation.
