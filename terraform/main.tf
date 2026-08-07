locals {
  app_name = "vts"
}

# ── Data Sources: RITA's existing infrastructure ─────────────────────────────

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

data "aws_vpc" "rita" {
  tags = { Name = "rita-vpc" }
}

data "aws_subnet" "rita" {
  vpc_id = data.aws_vpc.rita.id
  tags   = { Name = "rita-subnet-public" }
}

data "aws_security_group" "rita" {
  vpc_id = data.aws_vpc.rita.id
  name   = "rita-sg"
}

data "aws_internet_gateway" "rita" {
  filter {
    name   = "attachment.vpc-id"
    values = [data.aws_vpc.rita.id]
  }
}

# ── Networking: VtS subnet in RITA's VPC ─────────────────────────────────────

resource "aws_subnet" "vts" {
  vpc_id                  = data.aws_vpc.rita.id
  cidr_block              = var.vts_subnet_cidr
  map_public_ip_on_launch = true
  tags = {
    Name = "${local.app_name}-subnet-public"
  }
}

resource "aws_route_table" "vts" {
  vpc_id = data.aws_vpc.rita.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = data.aws_internet_gateway.rita.id
  }
  tags = {
    Name = "${local.app_name}-rt"
  }
}

resource "aws_route_table_association" "vts" {
  subnet_id      = aws_subnet.vts.id
  route_table_id = aws_route_table.vts.id
}

# ── Security Group ────────────────────────────────────────────────────────────

resource "aws_security_group" "vts" {
  name        = "${local.app_name}-sg"
  description = "VtS: app port from RITA only, SSH from anywhere"
  vpc_id      = data.aws_vpc.rita.id

  ingress {
    description     = "App port from RITA gateway"
    from_port       = 8743
    to_port         = 8743
    protocol        = "tcp"
    security_groups = [data.aws_security_group.rita.id]
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ── IAM Role — EC2 → CloudWatch Logs ─────────────────────────────────────────

resource "aws_iam_role" "vts_ec2" {
  name = "${local.app_name}-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "vts_cw_logs" {
  role       = aws_iam_role.vts_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

resource "aws_iam_instance_profile" "vts_ec2" {
  name = "${local.app_name}-ec2-profile"
  role = aws_iam_role.vts_ec2.name
}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "vts_app" {
  name              = "/vts/app"
  retention_in_days = var.log_retention_days
  tags              = { Name = "${local.app_name}-logs" }
}

# ── Alerting: SNS topic + email subscription ──────────────────────────────────

resource "aws_sns_topic" "vts_alerts" {
  name = "${local.app_name}-alerts"
}

resource "aws_sns_topic_subscription" "vts_alerts_email" {
  topic_arn = aws_sns_topic.vts_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── CloudWatch Alarms ────────────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "vts_cpu_high" {
  alarm_name          = "${local.app_name}-cpu-high"
  alarm_description   = "VtS EC2 CPU > 80% for 10 min"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_actions       = [aws_sns_topic.vts_alerts.arn]
  ok_actions          = [aws_sns_topic.vts_alerts.arn]
  dimensions          = { InstanceId = aws_instance.vts.id }
}

resource "aws_cloudwatch_metric_alarm" "vts_status_check" {
  alarm_name          = "${local.app_name}-status-check-failed"
  alarm_description   = "VtS EC2 system status check failed — auto-recovery triggered"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed_System"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_actions       = [
    "arn:aws:automate:${var.aws_region}:ec2:recover",
    aws_sns_topic.vts_alerts.arn,
  ]
  dimensions = { InstanceId = aws_instance.vts.id }
}

resource "aws_cloudwatch_log_metric_filter" "vts_errors" {
  name           = "${local.app_name}-error-lines"
  log_group_name = aws_cloudwatch_log_group.vts_app.name
  pattern        = "{ $.level = \"error\" }"
  metric_transformation {
    name      = "VtsErrorCount"
    namespace = "Vts/App"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "vts_app_errors" {
  alarm_name          = "${local.app_name}-app-errors"
  alarm_description   = "VtS application logged >= 3 errors in 5 minutes"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "VtsErrorCount"
  namespace           = "Vts/App"
  period              = 300
  statistic           = "Sum"
  threshold           = 3
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.vts_alerts.arn]
  dimensions          = {}
}

# ── SSH Key Pair ──────────────────────────────────────────────────────────────

resource "tls_private_key" "vts" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "vts" {
  key_name   = "${local.app_name}-key"
  public_key = tls_private_key.vts.public_key_openssh
}

resource "local_file" "private_key" {
  content         = tls_private_key.vts.private_key_pem
  filename        = "${path.module}/generated-key.pem"
  file_permission = "0400"
}

# ── EC2 Instance ──────────────────────────────────────────────────────────────

resource "aws_instance" "vts" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.vts.id
  vpc_security_group_ids = [aws_security_group.vts.id]
  key_name               = aws_key_pair.vts.key_name
  iam_instance_profile   = aws_iam_instance_profile.vts_ec2.name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = <<-EOF
    #!/bin/bash
    set -e

    # 1. Add 2 GB swap
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab

    # 2. Data directories — bind-mounted into the VtS container
    mkdir -p /opt/vts/{audio/output,phase1/output,phase2/output,phase3/output,phase4/output,phase5/output,phase6/output,phase7/output,phase8/output,eval/output,logs,run_status,cache}
    chown -R ubuntu:ubuntu /opt/vts

    # 3. Install Docker
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker ubuntu
    systemctl enable docker
    systemctl start docker
  EOF

  tags = {
    Name = "${local.app_name}-node"
  }
}
