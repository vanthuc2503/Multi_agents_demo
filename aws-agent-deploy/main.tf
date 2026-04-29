data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  owners = ["099720109477"] # Canonical
}

resource "aws_security_group" "agent_http" {
  name        = "${var.instance_name}-http"
  description = "Allow HTTP access for EC2 feasibility tests"

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.allowed_http_cidr]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.instance_name}-http"
  })
}

resource "aws_instance" "app_server" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.agent_http.id]
  user_data = templatefile("${path.module}/user_data.sh", {
    agent_api_key      = var.agent_api_key
    app_repository_url = var.app_repository_url
    app_repository_ref = var.app_repository_ref
  })
  user_data_replace_on_change = true

  tags = merge(var.tags, {
    Name = var.instance_name
  })
}
