# AWS Configuration Guide

This project is a small Data Engineering CI/CD demo that runs a Python Lambda
function from S3 object upload events and deploys the Lambda code through
GitHub Actions.

The repository does not currently include Terraform, CloudFormation, SAM, or
CDK. AWS resources are expected to be created in AWS first, then connected to
this repository through GitHub Actions variables and secrets.

## Architecture

```text
CSV file uploaded to S3 raw bucket
        |
        v
Lambda S3 trigger
        |
        v
AWS Lambda: lambda_function.handler
        |
        v
Read CSV from S3, normalize records, write JSONL output
        |
        v
S3 curated bucket or curated prefix
```

Code deployment is separate from data processing:

```text
Pull request to main
        |
        v
PR Checks workflow runs pytest
        |
        v
Merge to main
        |
        v
Deploy Lambda workflow assumes AWS IAM role through GitHub OIDC
        |
        v
aws lambda update-function-code uploads lambda_package.zip
```

## Repository AWS Touchpoints

| Area | File | Purpose |
| --- | --- | --- |
| Lambda runtime code | `lambda/src/lambda_function.py` | Handles S3 events, reads CSV files, writes JSONL output. |
| Deployment workflow | `.github/workflows/deploy-lambda.yml` | Tests, packages, and deploys Lambda code to AWS. |
| PR validation workflow | `.github/workflows/pr-checks.yml` | Runs unit tests before merging changes to `main`. |
| Unit tests | `tests/test_lambda_function.py` | Tests parsing, normalization, JSONL output, and output key generation. |
| Local test dependencies | `requirements-dev.txt` | Installs local test dependencies, including `pytest`. |

## AWS Resources To Create

### 1. S3 Raw Bucket

Create or choose a bucket where source CSV files will be uploaded.

Example:

```text
s3://my-raw-bucket/raw/events/input.csv
```

This bucket is configured as the event source for the Lambda trigger when CSV
objects are created.

### 2. S3 Curated Destination

The Lambda writes normalized JSONL output to S3.

There are two supported patterns:

| Pattern | Lambda environment configuration | Result |
| --- | --- | --- |
| Same bucket output | Leave `OUTPUT_BUCKET` unset. Set `OUTPUT_PREFIX`. | Output is written back to the source bucket under the configured prefix. |
| Separate curated bucket | Set `OUTPUT_BUCKET` to the curated bucket name. Set `OUTPUT_PREFIX`. | Output is written to a different bucket. |

Example output key:

```text
s3://my-curated-bucket/curated/events/run_date=2026-07-07/de_input.jsonl
```

The `run_date` partition is generated at runtime in UTC.

### 3. Lambda Function

Create a Lambda function with:

| Setting | Value |
| --- | --- |
| Runtime | Python 3.12 |
| Handler | `lambda_function.handler` |
| Deployment package shape | `lambda_function.py` must be at the zip root. |

The GitHub Actions workflow packages everything under `lambda/src`:

```bash
cd lambda/src
zip -r ../../lambda_package.zip .
```

Because of this, `lambda/src/lambda_function.py` becomes `lambda_function.py`
at the root of the zip package, which matches the handler setting.

### 4. Lambda Environment Variables

Configure these environment variables on the Lambda function:

| Variable | Required | Example | Description |
| --- | --- | --- | --- |
| `OUTPUT_BUCKET` | No | `my-curated-bucket` | Destination bucket for JSONL output. If unset, the Lambda writes to the source bucket. |
| `OUTPUT_PREFIX` | No | `curated/events` | Prefix for JSONL output. Defaults to `curated/events` in code. |

## IAM Configuration

There are two IAM roles involved:

1. Lambda execution role.
2. GitHub Actions deployment role.

### Lambda Execution Role

The Lambda execution role needs permission to read raw CSV objects and write
curated JSONL objects.

Example policy for separate raw and curated buckets:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadRawInputObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::my-raw-bucket/raw/events/*"
    },
    {
      "Sid": "WriteCuratedOutputObjects",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::my-curated-bucket/curated/events/*"
    },
    {
      "Sid": "WriteLambdaLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

If the Lambda reads and writes to the same bucket, adjust both S3 resources to
the same bucket and the correct prefixes.

### GitHub Actions Deployment Role

The deployment workflow uses GitHub OIDC through
`aws-actions/configure-aws-credentials@v4`. This avoids storing long-lived AWS
access keys in GitHub.

The role assumed by GitHub Actions needs permission to update the existing
Lambda function:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "UpdateLambdaCode",
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode"
      ],
      "Resource": "arn:aws:lambda:us-east-1:123456789012:function:de-cicd-demo"
    }
  ]
}
```

The role trust policy should allow the GitHub repository to assume the role
through OIDC. Replace `OWNER`, `REPO`, and account values:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:OWNER/REPO:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

## GitHub Actions Configuration

Configure these values in GitHub under:

```text
Settings -> Secrets and variables -> Actions
```

| Name | Type | Example | Used by |
| --- | --- | --- | --- |
| `AWS_ROLE_TO_ASSUME` | Secret | `arn:aws:iam::123456789012:role/github-actions-lambda-deploy` | `.github/workflows/deploy-lambda.yml` |
| `AWS_REGION` | Variable or secret | `us-east-1` | `.github/workflows/deploy-lambda.yml` |
| `LAMBDA_FUNCTION_NAME` | Variable or secret | `de-cicd-demo` | `.github/workflows/deploy-lambda.yml` |

The workflow reads `AWS_REGION` and `LAMBDA_FUNCTION_NAME` from repository
variables first, then falls back to secrets:

```yaml
aws-region: ${{ vars.AWS_REGION || secrets.AWS_REGION }}
--function-name "${{ vars.LAMBDA_FUNCTION_NAME || secrets.LAMBDA_FUNCTION_NAME }}"
```

Use repository variables for non-sensitive values and secrets for values you do
not want displayed in GitHub settings.

## Lambda Trigger

Configure an S3 trigger on the Lambda function:

| Setting | Recommended value |
| --- | --- |
| Trigger source | S3 |
| Source bucket | Raw bucket |
| Event type | `s3:ObjectCreated:*` |
| Prefix filter | `raw/events/` |
| Suffix filter | `.csv` |

This trigger invokes the Lambda when a matching CSV object is created in the raw
bucket. The incoming event still uses the standard S3 event shape. The handler
reads each record from:

```text
Records[].s3.bucket.name
Records[].s3.object.key
```

The code URL-decodes the object key with `unquote_plus`, so keys containing
spaces or special characters are supported.

## Data Contract

The Lambda expects CSV files with these headers:

| Column | Output behavior |
| --- | --- |
| `event_id` | Trimmed and written as `event_id`. |
| `customer_id` | Trimmed and written as `customer_id`. |
| `event_type` | Trimmed, lowercased, and written as `event_type`. |
| `amount` | Parsed as a decimal string. Invalid or empty values are omitted. |
| `event_ts` | Trimmed and written as `event_ts`. |

Each output record is enriched with:

| Field | Description |
| --- | --- |
| `pipeline_version` | Current value from `lambda/src/lambda_function.py`. |
| `processed_at` | UTC timestamp generated during processing. |

Output format is JSONL with content type `application/x-ndjson`.

## Deployment Flow

### Pull Request

When a pull request targets `main`, `.github/workflows/pr-checks.yml` runs if
the PR changes Lambda code, tests, dependencies, or the PR workflow.

The workflow:

1. Checks out the repository.
2. Sets up Python 3.12.
3. Installs `requirements-dev.txt`.
4. Runs `pytest`.

### Merge To Main

When changes are merged to `main`, `.github/workflows/deploy-lambda.yml` runs
if the push changes `lambda/**` or the deployment workflow.

The workflow:

1. Checks out the repository.
2. Sets up Python 3.12.
3. Installs test dependencies.
4. Runs `pytest`.
5. Assumes the AWS deployment role through GitHub OIDC.
6. Creates `lambda_package.zip` from `lambda/src`.
7. Runs `aws lambda update-function-code`.

The workflow can also be triggered manually with `workflow_dispatch`.

## Local Validation

Run unit tests before pushing changes:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## AWS Validation Checklist

After configuring AWS and GitHub:

1. Upload a sample CSV to the raw S3 prefix.
2. Confirm the Lambda function is invoked.
3. Check CloudWatch Logs for processing output or errors.
4. Confirm a JSONL file appears under the curated output prefix.
5. Merge a small Lambda code change to `main`.
6. Confirm the deploy workflow passes.
7. Confirm the Lambda function code was updated in AWS.

## Common Issues

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Deploy workflow cannot assume AWS role | OIDC provider or trust policy is missing or does not match the repository/branch. | Check the IAM OIDC provider and the role trust policy `sub` condition. |
| Deploy workflow gets `AccessDenied` on Lambda update | Deployment role lacks `lambda:UpdateFunctionCode`. | Add permission for the exact Lambda function ARN. |
| Lambda is not triggered by S3 uploads | Lambda S3 trigger is missing, disabled, or filters do not match object keys. | Check the Lambda trigger source bucket, prefix filter, suffix filter, and trigger status. |
| Lambda gets `AccessDenied` reading input | Lambda execution role lacks `s3:GetObject`. | Grant read permission to the raw bucket prefix. |
| Lambda gets `AccessDenied` writing output | Lambda execution role lacks `s3:PutObject`. | Grant write permission to the curated bucket prefix. |
| Output appears in the raw bucket unexpectedly | `OUTPUT_BUCKET` is unset. | Set `OUTPUT_BUCKET` to the curated bucket name if using a separate bucket. |
| Handler import fails after deployment | Lambda handler or package layout is wrong. | Set handler to `lambda_function.handler` and package files from `lambda/src`. |

## Minimal Configuration Summary

At minimum, this codebase needs:

1. An AWS Lambda function running Python 3.12 with handler
   `lambda_function.handler`.
2. A raw S3 bucket or prefix for CSV uploads.
3. A curated S3 bucket or prefix for JSONL output.
4. Lambda execution role permissions for S3 read, S3 write, and CloudWatch Logs.
5. A Lambda S3 trigger for raw CSV uploads.
6. A GitHub Actions OIDC IAM role with `lambda:UpdateFunctionCode`.
7. GitHub Actions values for `AWS_ROLE_TO_ASSUME`, `AWS_REGION`, and
   `LAMBDA_FUNCTION_NAME`.
