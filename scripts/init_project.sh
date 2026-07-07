#!/bin/bash

# Book Finder Agent Project Initialization Script
# This script sets up the development environment for the Book Finder Agent
#
# Usage: bash scripts/init_project.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
echo_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

echo_success() {
    echo -e "${GREEN}✓${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo_error() {
    echo -e "${RED}✗${NC} $1"
}

echo_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
}

# Check if script is running from project root
if [ ! -f "requirements.txt" ]; then
    echo_error "requirements.txt not found. Please run this script from the project root directory."
    exit 1
fi

# Initialize
echo_header "Book Finder Agent - Project Initialization"

# Step 1: Check Python version
echo_info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo_error "Python 3 is not installed. Please install Python 3.9+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}' | cut -d. -f1,2)
echo_success "Python $PYTHON_VERSION found"

# Step 2: Check Docker (optional)
echo_info "Checking for Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    echo_success "Docker $DOCKER_VERSION is installed"
else
    echo_warning "Docker is not installed. Some features may be unavailable. Install from: https://www.docker.com/get-docker"
fi

# Step 3: Check Docker Compose (if Docker is available)
if command -v docker &> /dev/null; then
    echo_info "Checking for Docker Compose..."
    if command -v docker-compose &> /dev/null; then
        echo_success "Docker Compose is installed"
    else
        echo_warning "Docker Compose v1 not found (Docker Compose v2 may be available as 'docker compose')"
    fi
fi

# Step 4: Create virtual environment
echo_header "Setting up Python Virtual Environment"

if [ -d ".venv" ]; then
    echo_warning "Virtual environment already exists at .venv"
    read -p "Do you want to recreate it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo_info "Removing existing virtual environment..."
        rm -rf .venv
    else
        echo_info "Skipping virtual environment creation"
    fi
fi

if [ ! -d ".venv" ]; then
    echo_info "Creating virtual environment..."
    python3 -m venv .venv
    echo_success "Virtual environment created"
fi

# Step 5: Activate virtual environment and install dependencies
echo_info "Activating virtual environment and installing dependencies..."
source .venv/bin/activate

echo_info "Upgrading pip, setuptools, and wheel..."
pip install --quiet --upgrade pip setuptools wheel
echo_success "pip, setuptools, wheel upgraded"

echo_info "Installing project dependencies..."
pip install --quiet -r requirements.txt
echo_success "Dependencies installed"

# Step 6: Setup environment file
echo_header "Environment Configuration"

if [ -f ".env" ]; then
    echo_warning ".env file already exists"
    read -p "Do you want to regenerate it from .env.example? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo_info "Copying .env.example to .env..."
        cp .env.example .env
        echo_success ".env created from .env.example"
        echo_warning "Please update .env with your actual configuration values (API keys, database credentials, etc.)"
    fi
else
    echo_info "Copying .env.example to .env..."
    cp .env.example .env
    echo_success ".env created from .env.example"
    echo_warning "Please update .env with your actual configuration values (API keys, database credentials, etc.)"
fi

# Step 7: Create directories
echo_header "Creating Project Directories"

DIRECTORIES=("logs" "scripts" "tests" "queries")
for dir in "${DIRECTORIES[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo_success "Created directory: $dir"
    else
        echo_info "Directory already exists: $dir"
    fi
done

# Step 8: Check code quality tools
echo_header "Checking Code Quality Tools"

echo_info "Installing development tools..."
pip install --quiet pytest pytest-cov pytest-watch black isort flake8 pylint bandit mkdocs
echo_success "Development tools installed"

# Step 9: Summary
echo_header "Initialization Complete!"

echo -e "${GREEN}Setup Summary:${NC}"
echo "  ✓ Python version: $PYTHON_VERSION"
echo "  ✓ Virtual environment: .venv"
echo "  ✓ Dependencies installed"
echo "  ✓ Environment file: .env"
echo "  ✓ Project directories created"
echo "  ✓ Development tools installed"

echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  1. Update .env with your API keys and database credentials"
echo "  2. Start development: make dev-docker"
echo "  3. Run tests: make test"
echo "  4. Build documentation: make docs"

echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "  make help               - Show all available commands"
echo "  make dev-docker         - Start development environment with Docker"
echo "  make test               - Run test suite"
echo "  make lint               - Check code style"
echo "  make format             - Auto-format code"
echo "  make quality            - Run all quality checks"

echo ""
echo_success "Project initialized successfully!"
echo ""

