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

---

**Subject:** Importer — the Mac crash, and two new flags

Hi Rodney,

That crash was `.DS_Store` — the hidden file Finder drops into every folder it
opens. The script treated it as a report, tried to read it as text, and fell
over on the first byte that isn't UTF-8. It only ever appears on your side,
which is why I never saw it here.

Two changes, both pushed:

- **Dot-files are ignored.** `.DS_Store` and anything else beginning with a dot
  is no longer picked up as a report.
- **One bad file no longer stops the run.** Before, `.DS_Store` failing meant
  your actual CSV never got imported — it was next in the list and the script
  had already died. Now an unreadable file is reported, left in `to_import/`,
  and the rest carry on. The run ends with a non-zero exit code so it's clear
  something was skipped.

Delete the `NGC7078.sqlite` the failed run left on your Desktop before you try
again, so the row counts start from clean.

I also noticed you're running this in `~/Desktop/m71` on an M71 report, but the
script defaults to `NGC7078.sqlite` — M15's database. So there are now two more
flags:

```
python3 import_NGC7078_Sloan_SG_v2_0.py --database M71.sqlite --table Sloan_SG
```

`--database` takes a filename (or a full path), `--table` takes a table name,
and each run prints where it's writing before it starts. Defaults are unchanged,
so your M15 runs need nothing new.

Worth deciding which you want for M71: its own database file, as above, or a
separate table inside the M15 one. Separate files are tidier if the two datasets
never get compared; one file with two tables is easier if you ever want to query
across both. Either works — say which and I'll set it up.

David
