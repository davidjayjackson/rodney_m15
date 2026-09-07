"""Load AAVSO extended-format photometry reports for NGC 7078 (M15) into SQLite.

The ``.csv`` and ``.txt`` files dropped in ``to_import/`` are parsed line by
line and inserted into the ``Sloan_SG`` table of ``NGC7078.sqlite``.  A file
must declare ``#TYPE=EXTENDED``, and one that imports at least one row is moved
to ``imported/`` so the next run only picks up new files.  Anything else is
named in the output and left where it is.

Usage:
    python import_NGC7078_Sloan_SG_v2_0.py
    python import_NGC7078_Sloan_SG_v2_0.py --keep      # leave files in to_import/
    python import_NGC7078_Sloan_SG_v2_0.py --project-path /some/other/m15
    python import_NGC7078_Sloan_SG_v2_0.py --database M71.sqlite --table Sloan_SG
"""

import argparse
import csv
import datetime
import sqlite3
import sys
from pathlib import Path

# Project home: the folder holding to_import/, imported/ and the database.
# Resolved from the script's own location so it works from any working directory.
PROJECT_HOME = Path(__file__).resolve().parent

# Defaults for --database and --table; both are overridable per run so one
# copy of the script can serve several clusters.
DEFAULT_DATABASE = 'NGC7078.sqlite'
DEFAULT_TABLE = 'Sloan_SG'

# The 15 columns of an AAVSO extended-format report, in file order.
FIELDS = [
    'STARNAME', 'DATE', 'MAG', 'MERR', 'FILT', 'TRANS', 'MTYPE',
    'CNAME', 'CMAG', 'KNAME', 'KMAG', 'AMASS', 'GROUP', 'CHART', 'NOTES',
]

# Columns stored as REAL; everything else is TEXT.
NUMERIC_FIELDS = {'DATE', 'MAG', 'MERR', 'CMAG', 'KMAG', 'AMASS', 'GROUP'}

# Natural key: one measurement of one star, at one Julian date, in one filter.
# Enforced by a unique index so a re-import cannot duplicate rows.
UNIQUE_FIELDS = ['STARNAME', 'DATE', 'FILT']

# AAVSO uses these placeholders for "not applicable"; store them as NULL.
NULL_TOKENS = {'', 'NA', 'N/A', '-'}

# Rows are written in chunks of this size rather than accumulating the whole
# file in memory.  The commit still happens once per file, so a file is all or
# nothing regardless of how many chunks it took.
BATCH_SIZE = 5000

# Reports arrive as .csv or .txt; anything else in to_import/ is left alone.
ALLOWED_SUFFIXES = {'.csv', '.txt'}


class FormatError(Exception):
    """The file is readable but is not an AAVSO extended-format report."""


def check_format(file_path):
    """Raise FormatError unless the file declares the AAVSO extended format.

    Only the leading ``#`` directives are read; the first data line ends the
    scan.  VPhot pads them out to the full column count, so ``#TYPE=EXTENDED``
    arrives as ``#TYPE=EXTENDED,,,,,,,,,,,,,,``.
    """
    with file_path.open(newline='', encoding='utf-8-sig') as data_file:
        for line in data_file:
            line = line.strip()
            if not line:
                continue
            if not line.startswith('#'):
                break
            directive = line.lstrip('#').split(',')[0].replace(' ', '').upper()
            if directive == 'TYPE=EXTENDED':
                return
    raise FormatError('no #TYPE=EXTENDED header')


def quote(name):
    """Quote an SQL identifier, so a name given on the command line is safe."""
    return '"%s"' % name.replace('"', '""')


class DataLine:
    """One measurement row from a report file."""

    __slots__ = FIELDS

    def __init__(self, values):
        if len(values) != len(FIELDS):
            raise ValueError(
                'expected %d fields, got %d' % (len(FIELDS), len(values))
            )
        for name, value in zip(FIELDS, values):
            setattr(self, name, value.strip())

    def as_row(self):
        """Return the values as a tuple ready for a parameterised insert."""
        row = []
        for name in FIELDS:
            value = getattr(self, name)
            if value.upper() in NULL_TOKENS:
                row.append(None)
            elif name in NUMERIC_FIELDS:
                row.append(float(value))
            else:
                row.append(value)
        return tuple(row)


def setup_db(database, table):
    """Create the table and its unique index if they do not already exist.

    The index is created separately rather than as a table constraint so that
    databases built by an earlier version of this script pick it up too.
    """
    columns = ', '.join(
        '"%s" %s' % (name, 'real' if name in NUMERIC_FIELDS else 'text')
        for name in FIELDS
    )
    database.execute(
        'create table if not exists %s (%s)' % (quote(table), columns)
    )

    key = ', '.join(quote(name) for name in UNIQUE_FIELDS)
    try:
        database.execute(
            'create unique index if not exists %s on %s (%s)'
            % (quote('%s_key' % table), quote(table), key)
        )
    except sqlite3.IntegrityError:
        raise SystemExit(
            'Cannot add the unique index: %s already holds rows that duplicate\n'
            'on (%s). Deduplicate the table before re-running.'
            % (table, ', '.join(UNIQUE_FIELDS))
        )
    database.commit()


def upsert_sql(table):
    """INSERT that overwrites the non-key columns when the row already exists.

    Lets a reprocessed stack correct the magnitudes of an earlier import
    instead of being discarded as a duplicate.
    """
    placeholders = ', '.join('?' * len(FIELDS))
    key = ', '.join(quote(name) for name in UNIQUE_FIELDS)
    assignments = ', '.join(
        '%s = excluded.%s' % (quote(name), quote(name))
        for name in FIELDS if name not in UNIQUE_FIELDS
    )
    return (
        'insert into %s values (%s) on conflict (%s) do update set %s'
        % (quote(table), placeholders, key, assignments)
    )


def import_file(database, table, file_path):
    """Insert every data line of ``file_path``.

    Returns (inserted, updated, failures).  A row whose (STARNAME, DATE, FILT)
    is already present has its remaining columns overwritten with the new
    values.
    """
    print('... importing %s ...' % file_path.name)
    failures = 0
    batch = []

    # total_changes counts inserts and updates together, so the growth in row
    # count tells us how many of those changes were new rows.  Both readings
    # are taken before the first write.
    count_sql = 'select count(*) from %s' % quote(table)
    rows_before = database.execute(count_sql).fetchone()[0]
    changes_before = database.total_changes
    sql = upsert_sql(table)

    with file_path.open(newline='', encoding='utf-8-sig') as data_file:
        for line_number, values in enumerate(csv.reader(data_file), start=1):
            # Skip blank lines and the '#TYPE=...' / '#NAME,DATE,...' headers.
            if not values or not values[0].strip() or values[0].lstrip().startswith('#'):
                continue
            try:
                batch.append(DataLine(values).as_row())
            except (ValueError, TypeError) as error:
                failures += 1
                print('    line %d skipped (%s): %s' % (line_number, error, ','.join(values)))
                continue
            if len(batch) >= BATCH_SIZE:
                database.executemany(sql, batch)
                batch.clear()

    if batch:
        database.executemany(sql, batch)
    database.commit()

    inserted = database.execute(count_sql).fetchone()[0] - rows_before
    updated = (database.total_changes - changes_before) - inserted
    if updated:
        print('    %d row(s) already present, updated in place' % updated)
    return inserted, updated, failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '--project-path', type=Path, default=PROJECT_HOME,
        help='folder holding to_import/, imported/ and the database (default: %(default)s)',
    )
    parser.add_argument(
        '--database', default=DEFAULT_DATABASE,
        help='SQLite file to write, absolute or relative to --project-path '
             '(default: %(default)s)',
    )
    parser.add_argument(
        '--table', default=DEFAULT_TABLE,
        help='table to write the measurements into (default: %(default)s)',
    )
    parser.add_argument(
        '--keep', action='store_true',
        help='do not move files to imported/ after a successful import',
    )
    args = parser.parse_args(argv)

    database_path = Path(args.database)
    if not database_path.is_absolute():
        database_path = args.project_path / database_path

    to_import_folder = args.project_path / 'to_import'
    imported_folder = args.project_path / 'imported'
    to_import_folder.mkdir(exist_ok=True)
    imported_folder.mkdir(exist_ok=True)

    # New files are the ones not yet moved over to imported/.  Dot-files are
    # skipped: macOS leaves a binary .DS_Store in every folder Finder opens.
    already_imported = {p.name for p in imported_folder.iterdir() if p.is_file()}
    files = []
    ignored = []
    for candidate in sorted(to_import_folder.iterdir()):
        if (not candidate.is_file()
                or candidate.name.startswith('.')
                or candidate.name in already_imported):
            continue
        if candidate.suffix.lower() in ALLOWED_SUFFIXES:
            files.append(candidate)
        else:
            ignored.append(candidate.name)

    # Named rather than passed over in silence, so a report saved under an
    # unexpected extension does not look like it was imported.
    if ignored:
        print('Ignored, not %s: %s'
              % (' or '.join(sorted(ALLOWED_SUFFIXES)), ', '.join(ignored)))

    if not files:
        print('Nothing to import in %s' % to_import_folder)
        return 0

    print('Files to import: %s' % ', '.join(p.name for p in files))
    print('Writing to %s, table %s' % (database_path, args.table))

    success = 0
    updates = 0
    failures = 0
    left_behind = []
    start_time = datetime.datetime.now()

    with sqlite3.connect(database_path) as database:
        setup_db(database, args.table)
        for file_path in files:
            # One unusable file should not abandon the files after it.  Its
            # partial writes are rolled back and it stays in to_import/.
            try:
                check_format(file_path)
                imported, refreshed, failed = import_file(
                    database, args.table, file_path
                )
            except (UnicodeDecodeError, csv.Error, FormatError) as error:
                database.rollback()
                left_behind.append(file_path.name)
                print('%s skipped: %s' % (file_path.name, error))
                continue
            success += imported
            updates += refreshed
            failures += failed
            if not imported and not refreshed:
                # Nothing reached the table, so the file is not imported in any
                # useful sense.  Moving it would make it look dealt with.
                left_behind.append(file_path.name)
                print('    no rows imported, left in to_import/')
            elif not args.keep:
                file_path.replace(imported_folder / file_path.name)

    elapsed = (datetime.datetime.now() - start_time).total_seconds()
    total = success + updates + failures
    ratio = failures / total if total else 0.0
    print('Time to import = %.1f seconds' % elapsed)
    print('Success = %d, Updated = %d, Failures = %d, ratio = %.7f'
          % (success, updates, failures, ratio))
    if left_behind:
        print('Left in %s: %s' % (to_import_folder, ', '.join(left_behind)))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
