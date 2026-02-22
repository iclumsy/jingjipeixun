"""Run students database migration with backup and report output."""
import argparse
import json
import os
from datetime import datetime

import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.student import migrate_db  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='Migrate students database schema and generate report.')
    parser.add_argument(
        '--db',
        default=os.path.join(PROJECT_ROOT, 'database', 'students.db'),
        help='Path to SQLite database file'
    )
    parser.add_argument(
        '--report',
        default='',
        help='Path to output migration report JSON (optional)'
    )
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if args.report:
        report_path = os.path.abspath(args.report)
    else:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = os.path.join(PROJECT_ROOT, 'database', f'migration_report_{ts}.json')

    report = migrate_db(db_path, create_backup=True, report_path=report_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nMigration report saved to: {report_path}")


if __name__ == '__main__':
    main()

