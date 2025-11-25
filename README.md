# Build & Push Docker image to AWS ECR

Minimal repo that contains a `Dockerfile` and a GitHub Actions workflow to build and push an image to Amazon ECR.

Required repository secrets (set these in GitHub):
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` (e.g. `us-east-1`)
- `ECR_REPOSITORY` (name of the ECR repo to push to)

Create an ECR repository (example PowerShell):

```powershell
aws ecr create-repository --repository-name my-app --region us-east-1
```

Local test (PowerShell):

```powershell
$region = 'us-east-1'
$repo = 'my-app'
$account = (aws sts get-caller-identity --query Account --output text)
docker build -t $repo:local .
docker tag $repo:local "$($account).dkr.ecr.$region.amazonaws.com/$repo:local"
aws ecr get-login-password --region $region | docker login --username AWS --password-stdin "$($account).dkr.ecr.$region.amazonaws.com"
docker push "$($account).dkr.ecr.$region.amazonaws.com/$repo:local"
```

Notes:
- The workflow runs on push to `main` and expects `ECR_REPOSITORY` to be configured in repo secrets.
- Adjust the branch name in `.github/workflows/docker-ecr.yml` as needed.
