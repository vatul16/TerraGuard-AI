# Security Group for RDS
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "Allow PostgreSQL from ECS"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "PostgreSQL from ECS/Bastion Host"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    security_groups = [
      aws_security_group.ecs_tasks.id,
      # aws_security_group.bastion.id
    ]
  }

  tags = {
    Name = "${var.project_name}-rds-sg"
  }
}

# RDS Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id
  tags = {
    Name = "${var.project_name}-db-subnet-group"
  }
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "postgres" {
  identifier        = "${var.project_name}-postgres"
  engine            = "postgres"
  engine_version    = "15.18"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_type      = "gp2"

  db_name  = "terraguard"
  username = "terraguard_admin"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az            = false
  publicly_accessible = false
  skip_final_snapshot = true # For dev only
  deletion_protection = false

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  tags = {
    Name = "${var.project_name}-postgres"
  }
}
