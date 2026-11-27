# OpenShift TLS Passthrough – Enterprise Orders Application

## Project Overview

This project demonstrates how to deploy a containerized Nginx application on Red Hat OpenShift and expose it securely using **TLS Passthrough Route termination**.

In this implementation, the OpenShift Router does not terminate HTTPS. Instead, encrypted TLS traffic passes through the router to the application Pod, where Nginx handles TLS termination using a certificate and private key stored in an OpenShift Secret.

## Architecture

```text
                  Client / Browser
                         |
                         | HTTPS :443
                         |
                         v
              OpenShift Router (HAProxy)
                  TLS Passthrough
                         |
                         | Encrypted TLS traffic
                         |
                         v
                  OpenShift Service
                     orders-pt
                         |
                 -------------------
                 |                 |
                 v                 v
            Application Pod  Application Pod
                 1                 2
                 |                 |
                 v                 v
              Nginx             Nginx
              :8443             :8443
                 |                 |
                 -------------------
                         |
                  TLS Termination
                         |
                         v
                  Enterprise Orders
                     Application
```

## Technology Stack

- Red Hat OpenShift
- Red Hat Developer Sandbox
- Kubernetes Deployments and Services
- OpenShift Routes
- TLS / SSL certificates
- Nginx
- Docker
- Quay Container Registry
- OpenSSL
- OpenShift CLI (`oc`)

## Key OpenShift Resources

| Resource | Name |
|---|---|
| Namespace | `kuslapur-dev` |
| Deployment | `orders-pt` |
| Service | `orders-pt` |
| Route | `orders-pt` |
| TLS Secret | `orders-pt-tls` |
| Application replicas | 2 |
| Nginx container port | 8443 |
| Service port | 443 |
| Route termination | Passthrough |

## 1. Create the Application

Create the project directory:

```bash
mkdir -p ocp-passthrough-lab/{app,nginx,certs}
cd ocp-passthrough-lab
```

Create the application HTML file at `app/index.html`.

The Enterprise Orders application displays a sample order dashboard with three sample orders.

## 2. Configure Nginx for HTTPS

Create `nginx/default.conf`:

```nginx
server {
    listen 8443 ssl;
    server_name _;

    ssl_certificate /etc/nginx/tls/tls.crt;
    ssl_certificate_key /etc/nginx/tls/tls.key;

    ssl_protocols TLSv1.2 TLSv1.3;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location /healthz {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

Nginx listens on port 8443 and uses the TLS certificate mounted from an OpenShift Secret.

## 3. Build the Container Image

Build the Nginx application image:

```bash
docker build -t orders-passthrough:v1 .
```

Tag the image for Quay:

```bash
docker tag orders-passthrough:v1 \
quay.io/YOUR_QUAY_USERNAME/orders-passthrough:v1
```

Push the image:

```bash
docker push \
quay.io/YOUR_QUAY_USERNAME/orders-passthrough:v1
```

Replace `YOUR_QUAY_USERNAME` with your Quay account username.

## 4. Create the OpenShift Service

Create `service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: orders-pt
spec:
  selector:
    app: orders-pt
  ports:
    - name: https
      port: 443
      targetPort: 8443
      protocol: TCP
  type: ClusterIP
```

Apply:

```bash
oc apply -f service.yaml
```

## 5. Create the Passthrough Route

Create the Route:

```bash
oc create route passthrough orders-pt \
  --service=orders-pt \
  --port=https
```

Retrieve the generated hostname:

```bash
HOST=$(oc get route orders-pt -o jsonpath='{.spec.host}')
echo "$HOST"
```

The Route uses TLS Passthrough, so the OpenShift Router forwards encrypted traffic to the backend application.

## 6. Generate a TLS Certificate

Generate a self-signed certificate using the actual Route hostname.

```bash
MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/tls.key \
  -out certs/tls.crt \
  -days 90 \
  -subj "/CN=$HOST/O=Enterprise" \
  -addext "subjectAltName=DNS:$HOST" \
  -addext "extendedKeyUsage=serverAuth"
```

The Subject Alternative Name (SAN) contains the Route hostname.

This is important because modern clients validate the hostname against the certificate SAN.

**Note:** This is a self-signed lab certificate, not a publicly trusted production certificate.

## 7. Create the TLS Secret

Create an OpenShift TLS Secret:

```bash
oc create secret tls orders-pt-tls \
  --cert=certs/tls.crt \
  --key=certs/tls.key
```

Verify:

```bash
oc get secret orders-pt-tls
```

The Secret contains:

- `tls.crt` – TLS certificate
- `tls.key` – Private key

## 8. Deploy the Application

Create `deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-pt
spec:
  replicas: 2
  selector:
    matchLabels:
      app: orders-pt
  template:
    metadata:
      labels:
        app: orders-pt
    spec:
      containers:
        - name: nginx
          image: quay.io/YOUR_QUAY_USERNAME/orders-passthrough:v1
          ports:
            - name: https
              containerPort: 8443
              protocol: TCP
          resources:
            requests:
              cpu: 100m
              memory: 64Mi
            limits:
              cpu: 300m
              memory: 128Mi
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8443
              scheme: HTTPS
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8443
              scheme: HTTPS
          securityContext:
            runAsNonRoot: true
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
            seccompProfile:
              type: RuntimeDefault
          volumeMounts:
            - name: tls-certs
              mountPath: /etc/nginx/tls
              readOnly: true
      volumes:
        - name: tls-certs
          secret:
            secretName: orders-pt-tls
            defaultMode: 0444
```

Replace the image reference with your actual Quay image.

Apply:

```bash
oc apply -f deployment.yaml
```

Check deployment status:

```bash
oc rollout status deployment/orders-pt
oc get pods -l app=orders-pt
```

## 9. Verify the Route and Service

Check the Route:

```bash
oc describe route orders-pt
```

Expected configuration:

```text
TLS Termination: passthrough
Service: orders-pt
Endpoint Port: https
```

Check the Service:

```bash
oc get svc orders-pt
```

Check the endpoints:

```bash
oc get endpointslices \
  -l kubernetes.io/service-name=orders-pt
```

Both application replicas should be available as backend endpoints.

## 10. Test the Application

Retrieve the Route hostname:

```bash
HOST=$(oc get route orders-pt -o jsonpath='{.spec.host}')
```

Test HTTPS:

```bash
curl -vk https://$HOST/
```

Expected response:

```text
HTTP/1.1 200 OK
Server: nginx
Content-Type: text/html
```

Expected application content:

```text
Enterprise Order Management
Application is running securely
Order Dashboard
ORD-1001 - Payment Processing
ORD-1002 - Order Completed
ORD-1003 - Order Pending
```

The `-k` flag skips certificate trust validation because the lab uses a self-signed certificate.

## 11. Verify the TLS Certificate

Inspect the certificate served by the application:

```bash
openssl s_client \
  -connect "${HOST}:443" \
  -servername "$HOST" </dev/null 2>/dev/null |
openssl x509 -noout -subject -issuer -dates -ext subjectAltName
```

Compare the local and remote SHA-256 fingerprints:

```bash
openssl x509 -in certs/tls.crt \
  -noout -fingerprint -sha256
```

```bash
openssl s_client \
  -connect "${HOST}:443" \
  -servername "$HOST" </dev/null 2>/dev/null |
openssl x509 -noout -fingerprint -sha256
```

Both fingerprints should match.

This demonstrates that the certificate configured in the application Pod is being served to the client through the passthrough Route.

## 12. TLS Termination Strategies

| Feature | Edge | Passthrough | Re-encrypt |
|---|---|---|---|
| Client-to-router TLS | Yes | Yes | Yes |
| Router decrypts traffic | Yes | No | Yes |
| Router-to-Pod TLS | No, normally HTTP | Yes, original encrypted connection | Yes, separate TLS connection |
| Backend certificate | Not required for router-to-Pod HTTP | Required | Required |
| Certificate configured on Route | Yes | No | Yes |
| Application manages TLS | No, for external TLS | Yes | Yes, for backend TLS |

### TLS Passthrough Flow

1. Client initiates HTTPS to the OpenShift Route.
2. Router reads the TLS Server Name Indication (SNI) to select the Route.
3. Router forwards encrypted TLS traffic to the Service.
4. Service forwards traffic to a ready application Pod.
5. Nginx terminates TLS using the mounted certificate and private key.
6. Nginx returns the application response through the same encrypted connection.

## 13. Troubleshooting Commands

Check Pods:

```bash
oc get pods -l app=orders-pt -o wide
```

Check Deployment:

```bash
oc describe deployment orders-pt
```

Check application logs:

```bash
oc logs deployment/orders-pt
```

Check the Service:

```bash
oc describe svc orders-pt
```

Check the Route:

```bash
oc describe route orders-pt
```

Validate Nginx configuration:

```bash
oc exec deployment/orders-pt -- nginx -t
```

Check mounted certificates:

```bash
oc exec deployment/orders-pt -- ls -l /etc/nginx/tls
```

## 14. Cleanup

Remove the resources created for this lab:

```bash
oc delete route orders-pt
oc delete service orders-pt
oc delete deployment orders-pt
oc delete secret orders-pt-tls
```

Optionally remove the local image:

```bash
docker rmi orders-passthrough:v1
```

## Key Learning Outcomes

After completing this project, you should understand:

- How OpenShift Routes expose applications externally.
- How TLS Passthrough works with SNI.
- How OpenShift Services distribute traffic across application Pods.
- How to generate self-signed TLS certificates with OpenSSL.
- How to store TLS certificates in OpenShift Secrets.
- How to mount Secrets into containers.
- How Nginx terminates TLS inside application Pods.
- How to validate HTTPS and inspect certificates.
- How to troubleshoot Routes, Services, Deployments, and Pods.

## Next Project

**OpenShift Re-encrypt TLS Termination**

Implement a separate TLS connection between the OpenShift Router and backend application Pods, configure the backend CA certificate, and verify both TLS connections.

---

**Project:** Enterprise Orders – OpenShift TLS Passthrough

**Environment:** Red Hat Developer Sandbox

**Focus:** OpenShift Networking, Routes, TLS, Nginx, Kubernetes Secrets, and Container Security
