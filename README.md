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

1. Bump the version number in `pyproject.toml`.
2. Commit and tag with version number.

   ```shell
   # for example, if new version is 1.2.3
   $ NEW_FOURGET_VERSION=1.2.3
   $ git add pyproject.toml
   $ git commit -m "Bump version to $NEW_FOURGET_VERSION"
   $ git tag -a "$NEW_FOURGET_VERSION" -m "$NEW_FOURGET_VERSION"
   $ git push
   ```

3. Run `poetry publish --build`. (Will need to have configured PYPI token)
