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
   $ git commit -m "Bump version to 1.2.3"
   $ git tag -a "1.2.3" -m "1.2.3"
   ```

3. Run `poetry publish --build`. (Will need to have configured PYPI token)
