from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class File:
    """A class to manage S3 file as a local file.

    Parameters
    ----------
    path : str | Path
        The path of the file. A local path or path to the S3 (s3://...) can be used.
    profile_name : str | None
        AWS profile name.
    aws_access_key_id : str | None
        AWS access key id.
    aws_secret_access_key : str | None
        AWS secret access key.
    aws_session_token : str | None
        AWS session token.
    region_name : str | None
        AWS region name.
    role_arn : str | None
        AWS role arn for Assume role. If this is set, aws_access_key_id,
        aws_secret_access_key, aws_session_token are replaced by Assume role.
    session_name : str
        AWS session name. Default is "s3_reader".
    retry_mode : str
        Retry mode for failed requests. Default is "standard".
    max_attempts : int
        Maximum number of retry attempts for failed requests. Default is 10.
    """

    path: str | Path
    profile_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None
    role_arn: str | None = None
    session_name: str = "boto3_session"
    retry_mode: str = "standard"
    max_attempts: int = 10

    def __post_init__(self) -> None:
        self.orig_path = self.path
        self.path = self.fix_path(self.path)
        self.tmp_file: tempfile._TemporaryFileWrapper[bytes] | None = None
        if self.path.startswith("s3:"):
            self.path = self.download_s3_file()

    def __del__(self) -> None:
        if self.tmp_file is not None:
            self.tmp_file.close()

    @staticmethod
    def fix_path(path: str | Path) -> str:
        if not path:
            return ""
        # remove double slash during the path (other than starting of s3://)
        if ":/" in str(path):
            pathes = str(path).split(":/")
            return f"{pathes[0]}:/{Path(pathes[1])}"
        return str(Path(path))

    @staticmethod
    def extract_s3_info(path: str | Path) -> tuple[str, str, str]:
        path = str(path)
        split_path = path.split("/")
        bucket_name = split_path[2]
        file_name = "/".join(split_path[3:])
        file_extension = split_path[-1].split(".")[-1]
        return bucket_name, file_name, file_extension

    def download_s3_file(self) -> str:
        # boto3.session.Session(profile_name=self.s3_profile).resource("s3") uses random.
        # To avoid unnoticed change of random state, restore random state after the process.
        import random

        from boto3_session import Session

        state = random.getstate()

        bucket_name, file_name, file_extension = self.extract_s3_info(
            self.path
        )
        temp_file = tempfile.NamedTemporaryFile(suffix=f".{file_extension}")

        s3 = Session(
            profile_name=self.profile_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            region_name=self.region_name,
            role_arn=self.role_arn,
            session_name=self.session_name,
            retry_mode=self.retry_mode,
            max_attempts=self.max_attempts,
        ).resource("s3")
        bucket = s3.Bucket(bucket_name)
        bucket.download_file(file_name, temp_file.name)
        self.tmp_file = temp_file

        random.setstate(state)

        return temp_file.name
