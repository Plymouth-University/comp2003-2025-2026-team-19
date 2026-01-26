# Web frontend

## Running the web server for development

### Prerequisites

uvicorn must be installed:

```sh
python -m pip install uvicorn
```

```sh
python -m uvicorn main:app --port 3001 --host 0.0.0.0
```

## Running the web server in production

### Prerequisites

docker and docker-compose must be installed

### Steps

1. Build the Docker image:
    ```sh
    $ docker build -t ferry.web.frontend .
    ```

2. Run the Docker container:
    ```sh
    $ docker run -p 3000:8000 ferry.web.frontend
    ```

3. Access the web application at [http://localhost:3000](http://localhost:3000)

**! IMPORTANT !** - You will need to rebuild each time you make changes to see any updates

## Notes