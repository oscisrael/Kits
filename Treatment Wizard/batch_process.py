"""
Batch VIN Processing Script
Usage:
    python batch_process.py vins_panamera.txt --force
    python batch_process.py vins_panamera.txt
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import subprocess


class BatchProcessor:
    """Process multiple VINs from a file"""

    def __init__(self, vins_file: str, force: bool = False, base_path: str = None):
        self.vins_file = Path(vins_file)
        self.force = force
        self.base_path = base_path
        self.results = {
            'success': [],
            'failed': [],
            'skipped': []
        }

    def load_vins(self):
        """Load VINs from file"""
        if not self.vins_file.exists():
            print(f"❌ קובץ VINs לא נמצא: {self.vins_file}")
            return []

        vins = []
        with open(self.vins_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                vin = line.strip()
                # דלג על שורות ריקות והערות
                if not vin or vin.startswith('#'):
                    continue

                # בדיקה שהVIN תקין
                if len(vin) != 17:
                    print(f"⚠️ שורה {line_num}: VIN לא תקין (אורך {len(vin)}): {vin}")
                    self.results['skipped'].append((vin, f"Invalid length: {len(vin)}"))
                    continue

                vins.append(vin)

        return vins

    def process_vin(self, vin: str):
        """Process a single VIN using main.py"""
        print("\n" + "=" * 70)
        print(f"🚗 מעבד VIN: {vin}")
        print("=" * 70)

        # בניית הפקודה
        cmd = [sys.executable, "main.py", vin]

        if self.force:
            cmd.append("--force")

        if self.base_path:
            cmd.extend(["--base-path", self.base_path])

        try:
            # הרצת main.py
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            # הדפסת הפלט
            print(result.stdout)

            if result.returncode == 0:
                print(f"✅ הצלחה: {vin}")
                self.results['success'].append(vin)
                return True
            else:
                print(f"❌ נכשל: {vin}")
                if result.stderr:
                    print(f"שגיאה: {result.stderr}")
                self.results['failed'].append((vin, result.stderr or "Unknown error"))
                return False

        except Exception as e:
            print(f"❌ שגיאה בעיבוד {vin}: {e}")
            self.results['failed'].append((vin, str(e)))
            return False

    def run(self):
        """Run batch processing"""
        start_time = datetime.now()

        print("=" * 70)
        print("🚀 Batch VIN Processing")
        print("=" * 70)
        print(f"קובץ VINs: {self.vins_file}")
        print(f"Force mode: {'ON' if self.force else 'OFF'}")
        if self.base_path:
            print(f"Base path: {self.base_path}")
        print("=" * 70)

        # טעינת VINs
        vins = self.load_vins()

        if not vins:
            print("❌ לא נמצאו VINs תקינים לעיבוד")
            return

        print(f"\n✅ נמצאו {len(vins)} VINs לעיבוד")

        # עיבוד כל VIN
        for i, vin in enumerate(vins, 1):
            print(f"\n{'=' * 70}")
            print(f"התקדמות: {i}/{len(vins)}")
            print(f"{'=' * 70}")

            self.process_vin(vin)

        # סיכום
        end_time = datetime.now()
        duration = end_time - start_time

        print("\n" + "=" * 70)
        print("📊 סיכום עיבוד")
        print("=" * 70)
        print(f"⏱️  זמן ריצה: {duration}")
        print(f"✅ הצליחו: {len(self.results['success'])}")
        print(f"❌ נכשלו: {len(self.results['failed'])}")
        print(f"⏭️  דולגו: {len(self.results['skipped'])}")
        print("=" * 70)

        # פירוט הצלחות
        if self.results['success']:
            print("\n✅ VINs שהצליחו:")
            for vin in self.results['success']:
                print(f"  • {vin}")

        # פירוט כישלונות
        if self.results['failed']:
            print("\n❌ VINs שנכשלו:")
            for vin, error in self.results['failed']:
                print(f"  • {vin}")
                if error:
                    print(f"    └─ {error[:100]}")

        # פירוט דילוגים
        if self.results['skipped']:
            print("\n⏭️  VINs שדולגו:")
            for vin, reason in self.results['skipped']:
                print(f"  • {vin} - {reason}")

        # שמירת דוח
        self.save_report()

        print("\n" + "=" * 70)
        if self.results['failed']:
            print("⚠️  העיבוד הסתיים עם שגיאות")
        else:
            print("🎉 כל ה-VINs עובדו בהצלחה!")
        print("=" * 70)

    def save_report(self):
        """Save processing report to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = Path(f"batch_report_{timestamp}.txt")

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("Batch Processing Report\n")
            f.write("=" * 70 + "\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"VINs file: {self.vins_file}\n")
            f.write(f"Force mode: {'ON' if self.force else 'OFF'}\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"Total VINs processed: {len(self.results['success']) + len(self.results['failed'])}\n")
            f.write(f"Success: {len(self.results['success'])}\n")
            f.write(f"Failed: {len(self.results['failed'])}\n")
            f.write(f"Skipped: {len(self.results['skipped'])}\n\n")

            if self.results['success']:
                f.write("Successful VINs:\n")
                f.write("-" * 70 + "\n")
                for vin in self.results['success']:
                    f.write(f"{vin}\n")
                f.write("\n")

            if self.results['failed']:
                f.write("Failed VINs:\n")
                f.write("-" * 70 + "\n")
                for vin, error in self.results['failed']:
                    f.write(f"{vin}\n")
                    if error:
                        f.write(f"  Error: {error}\n")
                f.write("\n")

            if self.results['skipped']:
                f.write("Skipped VINs:\n")
                f.write("-" * 70 + "\n")
                for vin, reason in self.results['skipped']:
                    f.write(f"{vin} - {reason}\n")

        print(f"\n📄 דוח נשמר ב: {report_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Batch VIN Processing - Process multiple VINs from a file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
דוגמאות שימוש:
  python batch_process.py vins_panamera.txt
  python batch_process.py vins_panamera.txt --force
  python batch_process.py vins_panamera.txt --force --base-path "C:\\Custom\\Path"

פורמט קובץ vins_panamera.txt:
  WP0ZZZ97ZLL132618
  WP0ZZZ976PL135008
  # זו הערה - תדלג
  WP0ZZZYA3SL047443
        """
    )

    parser.add_argument('vins_file', type=str,
                        help='קובץ טקסט עם רשימת VINs (שלדה אחת בכל שורה)')
    parser.add_argument('--force', action='store_true',
                        help='מצב force - דורס קבצים קיימים')
    parser.add_argument('--base-path', type=str, default=None,
                        help='נתיב בסיס לתיקיות הרכבים')

    args = parser.parse_args()

    processor = BatchProcessor(
        vins_file=args.vins_file,
        force=args.force,
        base_path=args.base_path
    )

    try:
        processor.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  העיבוד הופסק על ידי המשתמש")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ שגיאה קריטית: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
