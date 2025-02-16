import pathlib
import tempfile

from great_expectations.core.expectation_suite import ExpectationSuite
from great_expectations.core.yaml_handler import YAMLHandler
from great_expectations.data_context.data_context.file_data_context import (
    FileDataContext,
)

# This utility is not for general use. It is only to support testing.
from great_expectations.exceptions.exceptions import DataContextError
from tests.test_utils import get_redshift_connection_url

temp_dir = tempfile.TemporaryDirectory()
full_path_to_project_directory = pathlib.Path(temp_dir.name).resolve()
yaml: YAMLHandler = YAMLHandler()
CONNECTION_STRING = get_redshift_connection_url()

# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py imports">
import great_expectations as gx

context = gx.get_context(mode="file", project_root_dir=full_path_to_project_directory)
# </snippet>

# parse great_expectations.yml for comparison
great_expectations_yaml_file_path = pathlib.Path(
    full_path_to_project_directory, FileDataContext.GX_DIR, FileDataContext.GX_YML
)
great_expectations_yaml = yaml.load(great_expectations_yaml_file_path.read_text())

stores = great_expectations_yaml["stores"]
pop_stores = [
    "checkpoint_store",
    "validation_results_store",
    "validation_definition_store",
]
for store in pop_stores:
    stores.pop(store)

actual_existing_expectations_store = {}
actual_existing_expectations_store["stores"] = stores
actual_existing_expectations_store["expectations_store_name"] = great_expectations_yaml[
    "expectations_store_name"
]
expected_existing_expectations_store_yaml = """
# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py existing_expectations_store">
stores:
  expectations_store:
    class_name: ExpectationsStore
    store_backend:
      class_name: TupleFilesystemStoreBackend
      base_directory: expectations/

expectations_store_name: expectations_store
# </snippet>
"""

assert actual_existing_expectations_store == yaml.load(
    expected_existing_expectations_store_yaml
)

# adding expectations store
configured_expectations_store_yaml = """
# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py new_expectations_store">
stores:
  expectations_S3_store:
    class_name: ExpectationsStore
    store_backend:
      class_name: TupleS3StoreBackend
      bucket: '<YOUR S3 BUCKET NAME>'
      prefix: '<YOUR S3 PREFIX NAME>'  # Bucket and prefix in combination must be unique across all stores

expectations_store_name: expectations_S3_store
# </snippet>
"""

# replace example code with integration test configuration
configured_expectations_store = yaml.load(configured_expectations_store_yaml)
configured_expectations_store["stores"]["expectations_S3_store"]["store_backend"][
    "bucket"
] = "aws-golden-path-tests"
configured_expectations_store["stores"]["expectations_S3_store"]["store_backend"][
    "prefix"
] = "metadata/expectations"

# add and set the new expectation store
context.add_store(
    name=configured_expectations_store["expectations_store_name"],
    config=configured_expectations_store["stores"]["expectations_S3_store"],
)
with open(great_expectations_yaml_file_path) as f:
    great_expectations_yaml = yaml.load(f)
great_expectations_yaml["expectations_store_name"] = "expectations_S3_store"
great_expectations_yaml["stores"]["expectations_S3_store"]["store_backend"].pop(
    "suppress_store_backend_id"
)
with open(great_expectations_yaml_file_path, "w") as f:
    yaml.dump(great_expectations_yaml, f)

# adding validation results store
great_expectations_yaml_file_path = pathlib.Path(
    context.root_directory, FileDataContext.GX_YML
)
with open(great_expectations_yaml_file_path) as f:
    great_expectations_yaml = yaml.load(f)

stores = great_expectations_yaml["stores"]
# popping the rest out so that we can do the comparison. They aren't going anywhere dont worry
pop_stores = [
    "checkpoint_store",
    "expectations_store",
    "expectations_S3_store",
    "validation_definition_store",
]
for store in pop_stores:
    stores.pop(store)

actual_existing_validation_results_store = {}
actual_existing_validation_results_store["stores"] = stores
actual_existing_validation_results_store["validation_results_store_name"] = (
    great_expectations_yaml["validation_results_store_name"]
)

expected_existing_validation_results_store_yaml = """
# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py existing_validation_results_store">
stores:
  validation_results_store:
    class_name: ValidationResultsStore
    store_backend:
      class_name: TupleFilesystemStoreBackend
      base_directory: uncommitted/validations/

validation_results_store_name: validation_results_store
# </snippet>
"""

assert actual_existing_validation_results_store == yaml.load(
    expected_existing_validation_results_store_yaml
)

# adding validations store
configured_validation_results_store_yaml = """
# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py new_validation_results_store">
stores:
  validation_results_S3_store:
    class_name: ValidationResultsStore
    store_backend:
      class_name: TupleS3StoreBackend
      bucket: '<YOUR S3 BUCKET NAME>'
      prefix: '<YOUR S3 PREFIX NAME>'  # Bucket and prefix in combination must be unique across all stores
# </snippet>

# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py set_new_validation_results_store">
validation_results_store_name: validation_results_S3_store
# </snippet>
"""

# replace example code with integration test configuration
configured_validation_results_store = yaml.load(
    configured_validation_results_store_yaml
)
configured_validation_results_store["stores"]["validation_results_S3_store"][
    "store_backend"
]["bucket"] = "aws-golden-path-tests"
configured_validation_results_store["stores"]["validation_results_S3_store"][
    "store_backend"
]["prefix"] = "metadata/validations"

# add and set the new validation store
context.add_store(
    name=configured_validation_results_store["validation_results_store_name"],
    config=configured_validation_results_store["stores"]["validation_results_S3_store"],
)
with open(great_expectations_yaml_file_path) as f:
    great_expectations_yaml = yaml.load(f)
great_expectations_yaml["validation_results_store_name"] = "validation_results_S3_store"
great_expectations_yaml["stores"]["validation_results_S3_store"]["store_backend"].pop(
    "suppress_store_backend_id"
)
with open(great_expectations_yaml_file_path, "w") as f:
    yaml.dump(great_expectations_yaml, f)

# adding data docs store
data_docs_site_yaml = """
# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py add_data_docs_store">
data_docs_sites:
  local_site:
    class_name: SiteBuilder
    show_how_to_buttons: true
    store_backend:
      class_name: TupleFilesystemStoreBackend
      base_directory: uncommitted/data_docs/local_site/
    site_index_builder:
      class_name: DefaultSiteIndexBuilder
  S3_site:  # this is a user-selected name - you may select your own
    class_name: SiteBuilder
    store_backend:
      class_name: TupleS3StoreBackend
      bucket: <YOUR S3 BUCKET NAME>
    site_index_builder:
      class_name: DefaultSiteIndexBuilder
# </snippet>
"""

data_docs_site_yaml = data_docs_site_yaml.replace(
    "<YOUR S3 BUCKET NAME>", "demo-data-docs"
)
great_expectations_yaml_file_path = pathlib.Path(
    context.root_directory, FileDataContext.GX_YML
)
with open(great_expectations_yaml_file_path) as f:
    great_expectations_yaml = yaml.load(f)
great_expectations_yaml["data_docs_sites"] = yaml.load(data_docs_site_yaml)[
    "data_docs_sites"
]
with open(great_expectations_yaml_file_path, "w") as f:
    yaml.dump(great_expectations_yaml, f)


# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py vars">
datasource_name = "my_redshift_datasource"
connection_string = "redshift+psycopg2://<USER_NAME>:<PASSWORD>@<HOST>:<PORT>/<DATABASE>?sslmode=<SSLMODE>"
# </snippet>

# For tests, we are replacing the `connection_string`
connection_string = CONNECTION_STRING

# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py datasource">
datasource = context.data_sources.add_or_update_sql(
    name=datasource_name,
    connection_string=connection_string,
)
# </snippet>

# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py table_asset">
table_asset = datasource.add_table_asset(name="my_table_asset", table_name="taxi_data")
# </snippet>

# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py query_asset">
query_asset = datasource.add_query_asset(
    name="my_query_asset", query="SELECT * from taxi_data"
)
# </snippet>

# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py add_suite_and_get_validator">
request = table_asset.build_batch_request()

try:
    context.suites.add(ExpectationSuite(name="test_suite"))
except DataContextError:
    # If the suite already exists, we will get an error. We can ignore it.
    ...


validator = context.get_validator(
    batch_request=request, expectation_suite_name="test_suite"
)

print(validator.head())
# </snippet>

# <snippet name="docs/docusaurus/docs/snippets/aws_redshift_deployment_patterns.py validator_calls">
validator.expect_column_values_to_not_be_null(column="passenger_count")
validator.expect_column_values_to_be_between(
    column="congestion_surcharge", min_value=0, max_value=1000
)
# </snippet>
