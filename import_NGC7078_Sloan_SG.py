"""Load AAVSO extended-format photometry reports for NGC 7078 (M15) into SQLite.

Files dropped in ``to_import/`` are parsed line by line and inserted into the
``Sloan_SG`` table of ``NGC7078.sqlite``.  A file that imports cleanly is moved
to ``imported/`` so the next run only picks up new files.

Usage:
    python import_NGC7078_Sloan_SG.py
    python import_NGC7078_Sloan_SG.py --keep      # leave files in to_import/
    python import_NGC7078_Sloan_SG.py --project-path /some/other/m15
"""

import argparse
import csv
import datetime
import sqlite3
import sys
from pathlib import Path

DATABASE_NAME = 'NGC7078.sqlite'
TABLE_NAME = 'Sloan_SG'

# The 15 columns of an AAVSO extended-format report, in file order.
FIELDS = [
    'STARNAME', 'DATE', 'MAG', 'MERR', 'FILT', 'TRANS', 'MTYPE',
    'CNAME', 'CMAG', 'KNAME', 'KMAG', 'AMASS', 'GROUP', 'CHART', 'NOTES',
]

# Columns stored as REAL; everything else is TEXT.
NUMERIC_FIELDS = {'DATE', 'MAG', 'MERR', 'CMAG', 'KMAG', 'AMASS', 'GROUP'}

# AAVSO uses these placeholders for "not applicable"; store them as NULL.
NULL_TOKENS = {'', 'NA', 'N/A', '-'}


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


def setup_db(database):
    """Create the table if it does not already exist."""
    columns = ', '.join(
        '"%s" %s' % (name, 'real' if name in NUMERIC_FIELDS else 'text')
        for name in FIELDS
    )
    database.execute('create table if not exists "%s" (%s)' % (TABLE_NAME, columns))
    database.commit()


def import_file(database, file_path):
    """Insert every data line of ``file_path``.  Returns (successes, failures)."""
    print('... importing %s ...' % file_path.name)
    rows = []
    failures = 0

    with file_path.open(newline='', encoding='utf-8-sig') as data_file:
        for line_number, values in enumerate(csv.reader(data_file), start=1):
            # Skip blank lines and the '#TYPE=...' / '#NAME,DATE,...' headers.
            if not values or not values[0].strip() or values[0].lstrip().startswith('#'):
                continue
            try:
                rows.append(DataLine(values).as_row())
            except (ValueError, TypeError) as error:
                failures += 1
                print('    line %d skipped (%s): %s' % (line_number, error, ','.join(values)))

    placeholders = ', '.join('?' * len(FIELDS))
    database.executemany(
        'insert into "%s" values (%s)' % (TABLE_NAME, placeholders), rows
    )
    database.commit()
    return len(rows), failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '--project-path', type=Path, default=Path(__file__).resolve().parent,
        help='folder holding to_import/, imported/ and the database (default: this script\'s folder)',
    )
    parser.add_argument(
        '--keep', action='store_true',
        help='do not move files to imported/ after a successful import',
    )
    args = parser.parse_args(argv)

    to_import_folder = args.project_path / 'to_import'
    imported_folder = args.project_path / 'imported'
    to_import_folder.mkdir(exist_ok=True)
    imported_folder.mkdir(exist_ok=True)

    # New files are the ones not yet moved over to imported/.
    already_imported = {p.name for p in imported_folder.iterdir() if p.is_file()}
    files = sorted(
        p for p in to_import_folder.iterdir()
        if p.is_file() and p.name not in already_imported
    )

    if not files:
        print('Nothing to import in %s' % to_import_folder)
        return 0

    print('Files to import: %s' % ', '.join(p.name for p in files))

    success = 0
    failures = 0
    start_time = datetime.datetime.now()

    with sqlite3.connect(args.project_path / DATABASE_NAME) as database:
        setup_db(database)
        for file_path in files:
            imported, failed = import_file(database, file_path)
            success += imported
            failures += failed
            if not args.keep:
                file_path.replace(imported_folder / file_path.name)

    elapsed = (datetime.datetime.now() - start_time).total_seconds()
    total = success + failures
    ratio = failures / total if total else 0.0
    print('Time to import = %.1f seconds' % elapsed)
    print('Success = %d, Failures = %d, ratio = %.7f' % (success, failures, ratio))
    return 0


if __name__ == '__main__':
    sys.exit(main())
