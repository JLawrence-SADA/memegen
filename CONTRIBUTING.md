# Contributing

## Setup

### Requirements

* Make:
    * macOS: `$ xcode-select --install`
    * Linux: [https://www.gnu.org/software/make](https://www.gnu.org/software/make)
    * Windows: [https://mingw.org/download/installer](https://mingw.org/download/installer)
* Python: `$ pyenv install`
* Poetry: [https://poetry.eustace.io/docs/#installation](https://poetry.eustace.io/docs/#installation)

To confirm these system dependencies are configured correctly:

```text
$ make doctor
```

### Installation

Install project dependencies into a virtual environment:

```text
$ make install
```

## Local Development

To start the API server:

```text
$ make run
```

### Adding a Template

To add a new meme template:

1. Visit `/images/<my_new_template_key>`
2. Add a `default.png` (or JPG) background image in `templates` directory
3. Update `config.yml` in the `templates` directory
4. Refresh `/images/<my_new_template_key>` to see the sample meme

## Continuous Integration

### Manual

Run the tests:

```text
$ make test
```

Run static analysis:

```text
$ make check
```

### Automatic

Keep all of the above tasks running on change:

```text
$ make watch
```
