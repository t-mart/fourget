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
