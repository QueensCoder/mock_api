FROM apache/airflow:2.10.4-python3.12

USER root
RUN mkdir -p /opt/airflow/scripts /opt/airflow/duckdb
COPY etl/scripts/airflow_init.sh /opt/airflow/scripts/airflow_init.sh
RUN chmod +x /opt/airflow/scripts/airflow_init.sh

USER airflow
RUN pip install --no-cache-dir \
    apache-airflow-providers-postgres==5.12.0 \
    duckdb==1.1.3
