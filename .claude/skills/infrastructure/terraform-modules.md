---
name: terraform-modules
description: "Terraform Module Patterns — Terraform 모듈 개발 패턴 및 best practices. Use when working with infrastructure 도메인의 패턴 / 구현 선택."
effort: xhigh
deprecated: false
---

# Terraform Module Patterns

Terraform 모듈 개발 패턴 및 best practices.

## Module Structure

```
modules/vpc/
├── main.tf          # Resource definitions
├── variables.tf     # Input variables
├── outputs.tf       # Output values
├── versions.tf      # Version constraints
└── README.md        # Usage documentation
```

## variables.tf Template

```hcl
variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "Must be a valid CIDR block."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "private_subnet_cidrs" {
  description = "List of private subnet CIDR blocks"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}
```

## outputs.tf Template

```hcl
output "vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = aws_subnet.public[*].id
}
```

## versions.tf Template

```hcl
terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.0.0"
    }
  }
}
```

## locals.tf Template

```hcl
locals {
  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  name_prefix = "${var.project}-${var.environment}"
}
```

## Module Call

```hcl
module "vpc" {
  source = "../../modules/vpc"

  vpc_cidr    = var.vpc_cidr
  environment = var.environment
  project     = var.project

  private_subnet_cidrs = var.private_subnet_cidrs
  public_subnet_cidrs  = var.public_subnet_cidrs

  tags = local.common_tags
}

# Use module outputs
resource "aws_instance" "app" {
  subnet_id = module.vpc.private_subnet_ids[0]
}
```

## Naming Convention

```hcl
# Pattern: {project}-{env}-{resource}-{description}
resource "aws_vpc" "main" {
  tags = {
    Name = "${var.project}-${var.environment}-vpc"
  }
}

resource "aws_subnet" "private" {
  count = length(var.private_subnet_cidrs)
  tags = {
    Name = "${var.project}-${var.environment}-private-${count.index + 1}"
  }
}
```

## Variable Validation

```hcl
variable "instance_type" {
  type = string
  validation {
    condition     = can(regex("^t[23]\\.", var.instance_type))
    error_message = "Instance type must be t2.* or t3.*"
  }
}

variable "port" {
  type = number
  validation {
    condition     = var.port >= 1 && var.port <= 65535
    error_message = "Port must be between 1 and 65535."
  }
}
```

## Anti-patterns

| Mistake | Correct | Why |
|---------|---------|-----|
| No variable descriptions | Always add description | Documentation |
| No variable validation | Add validation blocks | Early error detection |
| No outputs | Export useful values | Module reusability |
| Hardcoded values | Use variables | Flexibility |
| No README.md | Document usage | User guidance |
| `count` for conditional | Use `for_each` or variable | Clearer intent |
