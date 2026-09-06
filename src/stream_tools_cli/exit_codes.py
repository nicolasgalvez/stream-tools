"""Exit codes for the `yt` CLI.

The CLI is a process boundary: a caller that shells out sees an exit code and
stdout, not an exception type. Uploads need more than success/failure, because
one failure mode is not safe to retry:

    0  success
    1  an error; retrying is reasonable
    2  the upload COMMITTED but confirmation was lost - never retry, the video
       exists on the channel. The recovered id is printed as "video_id: <id>"
       when it could be found.
    3  quota exhausted - stop the batch, the rest will fail too

1 stays the generic failure code so existing callers and scripts are unaffected.
"""

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_UPLOAD_COMMITTED = 2
EXIT_QUOTA_EXCEEDED = 3
