# Aws-cloud-backup-system

This repository provides a *very simple* Python utility for creating timestamped
backups of a local folder. It was created as a minimal example and can be
extended for use in larger automation or as part of a cloud backup pipeline.

## Script: `backup.py`

The script exposes a function `backup_files(source_folder, backup_folder)` that
copies the contents of the source directory into a newly created directory
inside the backup folder. The target directory is named
`backup_YYYY-MM-DD_HH-MM-SS` using the current date and time.

### Installation

No external dependencies are required beyond the Python standard library.

```sh
# run from repository root
python backup.py /path/to/source /path/to/backup-parent
```

or with interactive prompts:

```sh
python backup.py
```

The script also accepts command line arguments and will exit with a
non-zero code on failure.

### Example

```sh
$ python backup.py ~/Documents/project /mnt/backup
Backup completed successfully!
Backup location: /mnt/backup/backup_2026-02-26_14-30-00
```

The utility now supports a number of enhancements:

* **Incremental backups** – when you pass ``--incremental`` the script will
  compare to the most-recent backup and only copy new/modified files.
* **Encryption** – supply ``--encrypt`` (and optionally ``--password``) to
  archive and encrypt the result. This requires the ``cryptography`` package.
* **AWS integration** – after a backup is created you can upload it to S3 by
  specifying ``--s3-bucket`` and an optional ``--s3-prefix``. Directories are
  automatically tarred before transmission. The same binary/logical archive can
  also be sent directly to a Glacier vault using ``--glacier-vault`` for long
  term cold storage.

### Scheduling & CI/CD

A GitHub Actions workflow (see ``.github/workflows/ci.yml``) runs the test
suite and lints the code on every push/PR and also on a daily schedule. You
can also run the script from a cron job or other scheduler to perform regular
backups:

```cron
0 3 * * * /usr/bin/python /path/to/Aws-cloud-backup-system/backup.py \
    /home/user/data /mnt/backup --incremental --encrypt --password "s3cret" \
    --s3-bucket mybucket
```

### Running the tests

Install dependencies from ``requirements.txt`` and execute:

```sh
pip install -r requirements.txt
pytest -q
```
