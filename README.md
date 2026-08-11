# arches-he-location-extensions

An Arches application extension that provides location-based functionality and enhancements for Arches-based projects. Designed for easy integration with Arches projects (Historic England context).

## Requirements

- Python 3.10+ (Check the [Arches python requirements](https://arches.readthedocs.io/en/stable/installation/) and match your Python version)
- Arches ==7.6.22

## Contents Overview

This Arches application contains extensions that provide location management and location-related functionality for Arches-based heritage inventory systems.

- Generate Related Area Concept From Map function
- Generate Related Area From Map Function

## Installing for Development

For development purposes, you can treat this app as a standard Arches project. Either use the instructions for developing an Arches project or use the arches-containers configuration included in this repository.

### Standard Development Setup

```bash
pip install -e '/path/to/arches_he_location_extensions[dev]'
```

This installs the app in editable mode, allowing you to make changes and see them reflected immediately without needing to reinstall.

### Development Using arches-containers

This repository includes an `arches-containers` project configuration (requires version 1.1.0 or above), so you can import, activate, and start the system as follows:

1. Ensure Docker is installed and running.
2. Navigate to your workspace directory e.g. `~/workspaces/ahle_workspace`
3. Clone this repository if you haven't already.
4. Import the arches-container project configuration:

   ```bash
   act import -p arches_he_location_extensions
   ```

5. Activate the project:

   ```bash
   act activate -p arches_he_location_extensions
   ```

6. Start the system:

   ```bash
   act up
   ```

7. Once setup and webpack builds are complete, open a browser and navigate to `http://localhost:8002` or use `act view` in a terminal to open the project in your default browser.

For more details, see the [arches-containers documentation](https://github.com/HistoricEngland/arches-containers).

## Using This App in Your Arches Project

Follow these steps to add `arches-he-location-extensions` to your Arches project:

### 1. Add to `your_project/pyproject.toml`

Add the following to your `pyproject.toml` dependencies (in the `[project]` section):

```toml
dependencies = [
    "arches==7.6.22",
    "arches-he-location-extensions==1.0.0",
]


### 2. Update `your_project/your_project/settings.py`

Add the following to the appropriate locations:

```python
    FUNCTION_LOCATIONS.append("arches_he_location_extensions.functions")
```

Add to `INSTALLED_APPS` and `ARCHES_APPLICATIONS`:

```python
INSTALLED_APPS = (
    ...
    "your_project",
    "arches_he_location_extensions",
)

ARCHES_APPLICATIONS = ("arches_he_location_extensions",)
```

### 3. Update `your_project/your_project/urls.py`

Include the app's URLs (add project URLs before this):

```python
urlpatterns = [
    # ... your project urls ...
    path("", include("arches_he_location_extensions.urls")),
]
```

### 4. Run Database Migrations

Run the following command to apply any database migrations required by this app:

```bash
# If using arches-containers, run this in the application container
python manage.py migrate
```

### 5. Install and Build Front-End Dependencies

From the directory containing your `your_project/package.json`:

```bash
# If using arches-containers, run this in the application container or restart webpack
npm install
npm run build_development
```

### 6. Start Your Arches Project

```bash
python manage.py runserver

## Loading package for testing through the UI

To carry out testing through the UI, use the fixtures provided in the unit tests folder within the repo by running the [package load command](https://arches.readthedocs.io/en/stable/installing/projects-and-packages/#loading-a-package)

```bash
python manage.py packages -o load_package -s tests/fixtures/pkg
```

```

## License

This project is licensed under the GNU AGPLv3. See the LICENSE file for details.

## Additional Links

- [Code](https://github.com/HistoricEngland/arches-he-location-extensions)
- [Issues](https://github.com/HistoricEngland/arches-he-location-extensions/issues)
- [Pull requests](https://github.com/HistoricEngland/arches-he-location-extensions/pulls)
- [Arches Documentation](https://arches.readthedocs.io/)
