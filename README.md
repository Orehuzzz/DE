
# Airflow 
***
![airflow](pngs/project_overview.png)
# Airflow and Monitoring Stack

This repository contains a complete stack for running Apache Airflow alongside monitoring and alerting tools like Prometheus, Grafana, and more. It includes the setup for a BI database and visualization tools such as Superset, along with object storage via MinIO.

## Prerequisites

Ensure you have the following installed on your machine:
- Docker
- Docker Compose
- `dos2unix` (to convert `.sh` scripts if you use **Windows**)

## Directory Setup

Before running `docker-compose`, create the necessary directory for dags. Use the following command:
```bash 
mkdir dags
```
In case you'd like to make the data persistent, run the following commands:
```bash 
mkdir data
```
```bash 
mkdir data/custom_postgres_data data/minio_data data/superset_data data/prometheus_data data/grafana_data
```

## Preparing Shell Scripts

If you are running this setup on a Unix-based system, ensure all shell scripts in the `docker` directory are converted to Unix format:

```bash
find ./docker -type f -name "*.sh" -exec dos2unix {} \;
```

## Running the Stack

To start the entire stack, use the following command:

```bash
docker-compose up -d
```

To stop the stack, run:

```bash
docker-compose down
```

## Services and Access

Below is a table of all services, their ports, and default credentials:

| Service            | URL                     | Login        | Password        |
|---------------------|-------------------------|--------------|-----------------|
| **Airflow UI**      | [localhost:8088](http://localhost:8088) | `airflow`    | `airflow`      |
| **MinIO Console**   | [localhost:9001](http://localhost:9001) | `minio-root` | `minio-root`   |
| **Superset**        | [localhost:8088](http://localhost:8088) | `admin`      | `admin`        |
| **Grafana UI**      | [localhost:8443](http://localhost:8443) | `admin`      | `admin`        |
| **Prometheus**      | [localhost:9090](http://localhost:9090) | -            | -              |
| **Alertmanager**    | [localhost:9093](http://localhost:9093) | -            | -              |


## Features

1. **Airflow Orchestration**
   - Apache Airflow is configured with CeleryExecutor using Redis and PostgreSQL backend.
   - Supports DAG monitoring and task execution.

2. **Monitoring**
   - **Prometheus** collects metrics from Airflow.
   - **Grafana** visualizes the collected metrics with pre-configured dashboards.
   - **Alertmanager** triggers alerts for critical issues.

3. **BI and Visualization**
   - **Superset** is configured for BI and connects to a dedicated PostgreSQL instance.

4. **Object Storage**
   - **MinIO** is set up for S3-compatible object storage.