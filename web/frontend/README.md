# Web frontend

## Running the web server

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