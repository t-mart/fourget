# fourget

Download/scrape media files from 4chan threads

![Demo](https://raw.githubusercontent.com/t-mart/fourget/master/docs/demo.gif)

## Features

- fast concurrent downloading with asyncio
- skip download if already it already exists locally
- progress bar

## Example

```shell
$ fourget https://boards.4channel.org/g/thread/76759434
```

```shell
$ fourget --help
```

### `FileNotFoundError` on Windows

fourget will sometimes crash with a `FileNotFoundError` exception on Windows. This is due to
limitations on the maximum length a file path. However, this limitation can be removed by following
the steps at
<https://docs.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=cmd#enable-long-paths-in-windows-10-version-1607-and-later>.

## Installation

```shell
$ pip install fourget
```

## Releasing

1. Bump the version with `bump2version`, which also commits and tags.

   ```shell
   $ bump2version patch  # or minor or major, fmt: major.minor.patch
   $ git push
   ```

  The GitHub Actions CI workflow will take care of the rest.
