**Subject:** M15 importer — converted to Python 3

Hi Rodney,

Done — it's on `github.com/davidjayjackson/rodney_m15`. All 16,388 measurements
from your three Sloan g reports are loaded, no failures.

The old script had a syntax error and wouldn't actually parse, so it needed a
bit more than a 2-to-3 conversion. The README covers what changed, along with
setup and how to run it. Short version: nothing to install, drop new reports in
`to_import/` and run the script.

Two things worth knowing. The database now refuses duplicates, keyed on star +
Julian date + filter. And if you load a star and JD that's already there, the
new magnitudes overwrite the old — so reprocessing a stack corrects what's
stored, but nothing keeps the earlier values. If you'd want both kept, say so
and I'll change the table.

There's a logo and banner on the repo page too, drawn from your data: one dot
per star, sized by its real mean magnitude.

Last thing — I had a quick look for variables and found nothing that holds up.
The high-scatter stars are just noisy rather than pulsating. That's a statement
about this dataset, 68 points over five nights, not about M15.

David
