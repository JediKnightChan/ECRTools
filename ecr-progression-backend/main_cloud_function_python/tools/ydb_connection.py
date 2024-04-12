import logging
import os
import traceback

import ydb


class YDBConnector:
    def __init__(self, logger):
        self.logger = logger
        self.ydb_db_path = os.getenv("YDB_DB_PATH")
        if not self.ydb_db_path:
            raise ValueError("YDB DB PATH not specified")

        self.driver_config = ydb.DriverConfig(
            'grpcs://ydb.serverless.yandexcloud.net:2135',
            self.ydb_db_path,
            credentials=ydb.iam.ServiceAccountCredentials.from_file(
                os.path.join(os.path.dirname(__file__), "../authorized_key.json"))
        )

    def process_query(self, query, query_params):
        with ydb.Driver(self.driver_config) as driver:
            try:
                driver.wait(5)

                session = driver.table_client.session().create()

                prepared_query = session.prepare(query)
                r = session.transaction(ydb.SerializableReadWrite()).execute(
                    prepared_query, query_params,
                    commit_tx=True
                )

                return r, 0
            except TimeoutError:
                self.logger.error(f"YDB query raised timeout")
                return None, 1
            except Exception as e:
                self.logger.critical(
                    f"Error occurred while processing query {query} with "
                    f"params {query_params}: {traceback.format_exc()}"
                )
                return None, 2
