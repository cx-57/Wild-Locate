# Wild-Locate local browser app

## Intent

Try Wild-Locate in a normal browser on the user's computer, reusing the existing
species models and environmental datasets. Preserve the recently requested clean,
map-first presentation: compact controls, small result markers, and a collapsible
results table. This is a first browser version, not a public deployment.

## First-version scope

- Launch with `wildlocate web`, open the local URL in the default browser, and
  print the URL in the terminal. Ctrl+C shuts down the server and active analysis.
- Keep the existing `wildlocate` desktop launch behavior intact.
- Select a species from the bundled models available for the selected state.
- Select a center by clicking the map or typing latitude and longitude.
- Choose Point analysis or Regional analysis with 10, 25, or 50 km radius.
- Reuse existing point and 81-point regional analysis without changing scores.
- Display point score, percentile, category, model, and environmental values.
- Display regional circle, small colored markers, compact coverage/mean summary,
  clickable point details, and a collapsed-by-default full results table.
- Show clear validation and backend errors; distinguish missing data from low scores.
- Show elapsed time while working; allow cancellation and another analysis afterward.
- Export the current result as JSON. Clear obsolete results when selections change.
- Support a narrow browser window with controls above the map.

Account creation, custom-model management, training screens, and public hosting are
outside this first version. They remain available in the desktop app. States with
no bundled models show a clear unavailable state rather than an empty runnable form.

## Implementation approach

Use a small Python standard-library HTTP server and plain HTML/CSS/JavaScript.
This avoids adding a separate JavaScript build system or another Python framework
for the local prototype. An alternative is a framework such as FastAPI, which
would be more appropriate if this grows into a hosted multi-user service.

Keep new files grouped in `wildlocate/web/`: server code plus the browser page,
stylesheet, and script. Reuse the bundled Leaflet assets and license. Add all new
browser assets to package data so an installed build includes them.

The server binds only to `127.0.0.1`. Serve an explicit allowlist of frontend assets;
do not expose the repository or raw filesystem. Validate request origin/host and
use a per-launch request token for mutations, preventing unrelated websites from
starting local jobs. Reject oversized or malformed requests.

A small JSON API provides available states/species, starts an assessment, returns
job status/results, and cancels the current job. Use one active worker subprocess
at a time, with bounded in-memory job state. Reuse `core.prediction_worker` and its
existing JSON protocol. Keep prediction stdout separate from diagnostic stderr.
Cancellation terminates the worker, and the next assessment starts a fresh worker.
On shutdown, release the process and server resources.

The frontend polls job status while retaining full browser responsiveness. It
renders server-provided text as text, not executable HTML, and ignores obsolete
responses after cancellation or changed inputs. Missing map tiles do not disable
manual coordinate entry or textual results.

## Verification and acceptance

- Test static-file restrictions, input validation, available-model listings,
  prediction success/error responses, job cancellation, and restart.
- Test CLI parsing and preserve the current desktop/init/status commands.
- Exercise a real Massachusetts assessment with the existing local datasets.
- Verify the browser renders all scored grid points and the radius outline,
  expands/collapses the score table, and exports valid JSON.
- Inspect both wide and narrow layouts and verify keyboard-accessible controls.
- Check that the installed package includes the frontend assets.
- Run the existing suite and report any failures or live-verification limitations.

Success means the user can run `wildlocate web`, choose Bobcat and a center/radius,
and receive the same underlying analysis in a usable browser interface.
