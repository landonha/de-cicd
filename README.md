# DE CI/CD Lambda Demo

A small Data Engineering CI/CD example:

- The Lambda function receives S3 CSV upload events.
- It reads raw CSV files from S3.
- It standardizes fields and performs simple data cleaning.
- It writes curated JSONL output to another S3 prefix.
- GitHub Actions automatically deploys the code to AWS Lambda after changes are merged into `main`.

## Project Structure

```text
.
├── .github/workflows/deploy-lambda.yml
├── lambda/src/lambda_function.py
├── tests/test_lambda_function.py
├── requirements-dev.txt
└── README.md
```

## Lambda Environment Variables

| Variable | Example | Description |
| --- | --- | --- |
| `OUTPUT_BUCKET` | `my-curated-bucket` | Bucket for JSONL output. If unset, the Lambda writes back to the input bucket. |
| `OUTPUT_PREFIX` | `curated/events` | Output prefix for curated files. |

## Local Testing

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## GitHub Actions Deployment Configuration

Configure the following values in your GitHub repository under `Settings -> Secrets and variables -> Actions`:

| Secret / Variable | 示例 |
| --- | --- |
| `AWS_ROLE_TO_ASSUME` | `arn:aws:iam::123456789012:role/github-actions-lambda-deploy` |
| `AWS_REGION` | `us-east-1` |
| `LAMBDA_FUNCTION_NAME` | `de-cicd-demo` |

The workflow uses GitHub OIDC to authenticate with AWS, so no long-lived AWS access keys are required. When a PR is merged, GitHub creates a push to `main`; the workflow listens for pushes to `main` and performs the CD deployment.

## Minimum AWS Setup

1. Create a Lambda function with the Python 3.12 runtime and set the handler to `lambda_function.handler`.
2. Grant the Lambda execution role permission to read from the raw S3 bucket and write to the curated S3 bucket.
3. Grant the GitHub Actions OIDC role permission to call `lambda:UpdateFunctionCode`.
4. Configure an S3 event notification so CSV uploads to the raw bucket trigger the Lambda function.
