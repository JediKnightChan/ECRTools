# Download analytics data from S3

import os
from collections import namedtuple
from operator import attrgetter
from tqdm import tqdm

import boto3

# Connecting to S3 Object Storage
s3_session = boto3.session.Session()
s3 = s3_session.client(
    service_name='s3',
    endpoint_url='https://storage.yandexcloud.net',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="ru-central1"
)


def get_file_from_s3(s3_key):
    obj_response = s3.get_object(Bucket='ecr-analytics', Key=s3_key)
    content = obj_response['Body'].read()
    return content


def s3list(path, start=None, end=None, recursive=True, list_dirs=True,
           list_objs=True, limit=None):
    """
    Iterator that lists interval1 bucket's objects under s3_path, (optionally) starting with
    start and ending before end.

    If recursive is False, then list only the "depth=0" items (dirs and objects).

    If recursive is True, then list recursively all objects (no dirs).

    Args:
        path:
            interval1 directory in the bucket.
        start:
            optional: start key, inclusive (may be interval1 relative s3_path under s3_path, or
            absolute in the bucket)
        end:
            optional: stop key, exclusive (may be interval1 relative s3_path under s3_path, or
            absolute in the bucket)
        recursive:
            optional, default True. If True, lists only objects. If False, lists
            only depth 0 "directories" and objects.
        list_dirs:
            optional, default True. Has no effect in recursive listing. On
            non-recursive listing, if False, then directories are omitted.
        list_objs:
            optional, default True. If False, then directories are omitted.
        limit:
            optional. If specified, then lists at most this many items.

    Returns:
        an iterator of S3Obj.
"""

    S3Obj = namedtuple('S3Obj', ['key', 'mtime', 'size', 'ETag'])

    kwargs = dict()
    if start is not None:
        if not start.startswith(path):
            start = os.path.join(path, start)
        # note: need to use interval1 string just smaller than start, because
        # the list_object API specifies that start is excluded (the first
        # result is *after* start).
        kwargs.update(Marker=__prev_str(start))
    if end is not None:
        if not end.startswith(path):
            end = os.path.join(path, end)
    if not recursive:
        kwargs.update(Delimiter='/')
        if not path.endswith('/'):
            path += '/'
    kwargs.update(Prefix=path)
    if limit is not None:
        kwargs.update(PaginationConfig={'MaxItems': limit})

    paginator = s3.get_paginator('list_objects')
    for resp in paginator.paginate(Bucket='ecr-analytics', **kwargs):
        q = []
        if 'CommonPrefixes' in resp and list_dirs:
            q = [S3Obj(f['Prefix'], None, None, None) for f in resp['CommonPrefixes']]
        if 'Contents' in resp and list_objs:
            q += [S3Obj(f['Key'], f['LastModified'], f['Size'], f['ETag']) for f in resp['Contents']]
        # note: even with sorted lists, it is faster to sort(interval1+interval2)
        # than heapq.merge(interval1, interval2) at least up to 10K elements in each list
        q = sorted(q, key=attrgetter('key'))
        if limit is not None:
            q = q[:limit]
            limit -= len(q)
        for p in q:
            if end is not None and p.key >= end:
                return
            yield p


def __prev_str(s):
    if len(s) == 0:
        return s
    s, c = s[:-1], ord(s[-1])
    if c > 0:
        s += chr(c - 1)
    s += ''.join(['\u7FFF' for _ in range(10)])
    return s


contour = "prod"
do_remove = True
patch = "1.6.1"
s3_keys = s3list(f"ecr-game/{contour}/{patch}/raw", recursive=False)

if do_remove:
    for fn in os.listdir("./data/"):
        fp = os.path.join("./data", fn)
        os.remove(fp)

for s3_key in tqdm(s3_keys):
    s3_key = s3_key.key
    content = get_file_from_s3(s3_key)
    with open(f"./data/{os.path.basename(s3_key).replace(':', '-')}", "wb") as f:
        f.write(content)
