import sys

api_key, server_address = sys.argv[1], sys.argv[2]

###
# Workflow that loads a table from the `aqueduct_demo` then saves it to `table_1` in append mode.
# This save operator is then replaced by one that saves to `table_1` in replace mode.
# In the next deployment of this run, it saves to `table_1` in append mode.
# In the last deployment, it saves to `table_2` in append mode.
###

import aqueduct

name = "Test: Changing Saves"
client = aqueduct.Client(api_key, server_address)
integration = client.integration(name="aqueduct_demo")

###

table = integration.sql(query="SELECT * FROM wine;")

table.save(integration.config(table="table_1", update_mode="replace"))

flow = client.publish_flow(
    name=name,
    artifacts=[table],
)

###

table = integration.sql(query="SELECT * FROM wine;")

table.save(integration.config(table="table_1", update_mode="append"))

flow = client.publish_flow(
    name=name,
    artifacts=[table],
)

###

table = integration.sql(query="SELECT * FROM wine;")

table.save(integration.config(table="table_1", update_mode="append"))

flow = client.publish_flow(
    name=name,
    artifacts=[table],
)

###

table = integration.sql(query="SELECT * FROM wine;")

table.save(integration.config(table="table_2", update_mode="replace"))

flow = client.publish_flow(
    name=name,
    artifacts=[table],
)

###

print(flow.id(), 4)
