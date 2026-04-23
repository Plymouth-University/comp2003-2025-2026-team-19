# MQTT TLS Setup

## Prerequisites
 
- `openssl` installed and available on your PATH
- If using **Git Bash on Windows**, run this first to prevent path mangling:
  ```bash
  export MSYS_NO_PATHCONV=1
  ```

---

## Step 1 — Generate the Certificate Authority (CA)
 
The CA is used to sign the broker certificate. The `ca.crt` is what gets embedded in the ESP32 firmware so it can verify the broker.

```bash
# Generate the CA private key
openssl genrsa -out ca.key 2048
 
# Generate the CA certificate (self-signed, valid 10 years)
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt -subj "/CN=MyBrokerCA"
```

## Step 2 — Generate the Broker Certificate

The broker CN and SANs must match the hostname or IP address your ESP32 uses to connect. Modern TLS clients require at least one SAN — a CN alone is not sufficient.

```bash
# Generate the broker private key
openssl genrsa -out broker.key 2048
 
# Generate the broker certificate signing request (CSR)
openssl req -new -key broker.key -out broker.csr -subj "/CN=your-broker-hostname"
```

Verify the certificate was signed correctly:
 
```bash
openssl verify -CAfile ca.crt broker.crt
# Expected output: broker.crt: OK
```