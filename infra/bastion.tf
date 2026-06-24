# Securtiy Group for Bastion Host
resource "aws_security_group" "bastion" {
  name        = "${var.project_name}-bastion-sg"
  description = "Allow traffic from ssh to Bastion Host"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "From my IP/anywhere"
    from_port   = "22"
    to_port     = "22"
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"

    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-bastion-sg"
  }
}

# EC2 - Bastion Host
resource "aws_instance" "bastion" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = "t2.micro"
  subnet_id                   = aws_subnet.public[0].id
  vpc_security_group_ids      = [aws_security_group.bastion.id]
  associate_public_ip_address = true

  key_name = var.bastion_key_name

  tags = {
    Name = "${var.project_name}-bastion"
  }
}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true

  owners = ["137112412989"] # Amazon

  filter {
    name   = "name"
    values = ["al2023-ami-*-kernel-6.1-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}
