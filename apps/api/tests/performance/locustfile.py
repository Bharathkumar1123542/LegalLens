"""
Performance/Load Tests — LegalLens API
Uses Locust for load testing with 100 concurrent users (per architecture.md)
Target: P95 latency < 2s for read operations, < 5s for write operations
"""

import json
import random
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser


class LegalLensUser(FastHttpUser):
    """
    Simulates a typical LegalLens user workflow.
    
    User behavior:
    - Register/login
    - Upload document
    - Check document status
    - Simplify document
    - Extract clauses
    - Chat about document
    - Create comparison
    - Export results
    """
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Login and setup user state."""
        # Register user (or login if exists)
        self.email = f"loadtest_{random.randint(1000, 9999)}@example.com"
        self.password = "LoadTest123!"
        
        # Register
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "full_name": "Load Test User",
            },
            name="/auth/register",
        )
        
        if response.status_code == 201:
            data = response.json()
            self.token = data["access_token"]
        else:
            # Try login if registration failed (user exists)
            response = self.client.post(
                "/api/v1/auth/login",
                json={
                    "email": self.email,
                    "password": self.password,
                },
                name="/auth/login",
            )
            data = response.json()
            self.token = data["access_token"]
        
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.document_ids = []
    
    @task(3)
    def list_documents(self):
        """List user's documents (frequent operation)."""
        self.client.get(
            "/api/v1/documents",
            headers=self.headers,
            name="/documents [list]",
        )
    
    @task(1)
    def upload_document(self):
        """Upload a document (less frequent)."""
        # Simulate PDF file
        files = {
            "file": ("test_contract.pdf", b"%PDF-1.4\ntest content", "application/pdf")
        }
        
        response = self.client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=self.headers,
            name="/documents/upload",
        )
        
        if response.status_code == 201:
            data = response.json()
            self.document_ids.append(data["id"])
    
    @task(2)
    def get_document(self):
        """Get document details (common operation)."""
        if not self.document_ids:
            return
        
        doc_id = random.choice(self.document_ids)
        self.client.get(
            f"/api/v1/documents/{doc_id}",
            headers=self.headers,
            name="/documents/{id} [get]",
        )
    
    @task(1)
    def simplify_document(self):
        """Simplify document (occasional operation)."""
        if not self.document_ids:
            return
        
        doc_id = random.choice(self.document_ids)
        self.client.post(
            f"/api/v1/documents/{doc_id}/simplify",
            json={"reading_level": "8th_grade"},
            headers=self.headers,
            name="/documents/{id}/simplify",
        )
    
    @task(1)
    def extract_clauses(self):
        """Extract clauses from document."""
        if not self.document_ids:
            return
        
        doc_id = random.choice(self.document_ids)
        self.client.post(
            f"/api/v1/documents/{doc_id}/extract-clauses",
            headers=self.headers,
            name="/documents/{id}/extract-clauses",
        )
    
    @task(2)
    def chat_with_document(self):
        """Chat about document (frequent interaction)."""
        if not self.document_ids:
            return
        
        doc_id = random.choice(self.document_ids)
        questions = [
            "What are the termination clauses?",
            "What are my payment obligations?",
            "Are there any liability limitations?",
            "What is the confidentiality period?",
        ]
        
        self.client.post(
            f"/api/v1/chat/{doc_id}",
            json={"message": random.choice(questions)},
            headers=self.headers,
            name="/chat/{doc_id}",
        )
    
    @task(1)
    def create_comparison(self):
        """Create comparison between documents."""
        if len(self.document_ids) < 2:
            return
        
        # Pick 2 random documents
        doc_ids = random.sample(self.document_ids, 2)
        
        self.client.post(
            "/api/v1/comparisons",
            json={"document_ids": doc_ids},
            headers=self.headers,
            name="/comparisons [create]",
        )
    
    @task(1)
    def create_export(self):
        """Create export artifact."""
        if not self.document_ids:
            return
        
        doc_id = random.choice(self.document_ids)
        export_type = random.choice(["summary", "checklist", "lawyer_brief"])
        file_format = random.choice(["pdf", "docx", "md"])
        
        self.client.post(
            "/api/v1/exports",
            json={
                "document_id": doc_id,
                "export_type": export_type,
                "file_format": file_format,
            },
            headers=self.headers,
            name="/exports [create]",
        )


class ReadHeavyUser(FastHttpUser):
    """User that mostly reads (list, get, view operations)."""
    
    wait_time = between(0.5, 2)
    
    def on_start(self):
        """Setup with existing user."""
        self.email = "readonly@example.com"
        self.password = "ReadOnly123!"
        
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": self.email, "password": self.password},
            name="/auth/login",
        )
        
        if response.status_code == 200:
            data = response.json()
            self.token = data["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            # Create user if doesn't exist
            self.client.post(
                "/api/v1/auth/register",
                json={
                    "email": self.email,
                    "password": self.password,
                    "full_name": "Read Only User",
                },
                name="/auth/register",
            )
            response = self.client.post(
                "/api/v1/auth/login",
                json={"email": self.email, "password": self.password},
                name="/auth/login",
            )
            data = response.json()
            self.token = data["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(10)
    def list_documents(self):
        """Frequently list documents."""
        self.client.get(
            "/api/v1/documents",
            headers=self.headers,
            name="/documents [list]",
        )
    
    @task(1)
    def health_check(self):
        """Check API health."""
        self.client.get("/health", name="/health")


class WriteHeavyUser(FastHttpUser):
    """User that performs many write operations."""
    
    wait_time = between(2, 5)
    
    def on_start(self):
        """Setup user."""
        self.email = f"writer_{random.randint(1000, 9999)}@example.com"
        self.password = "Writer123!"
        
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "full_name": "Write Heavy User",
            },
            name="/auth/register",
        )
        
        data = response.json()
        self.token = data["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.document_ids = []
    
    @task(5)
    def upload_document(self):
        """Frequent uploads."""
        files = {
            "file": (f"doc_{random.randint(1, 999)}.pdf", b"%PDF-1.4\ntest", "application/pdf")
        }
        
        response = self.client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=self.headers,
            name="/documents/upload",
        )
        
        if response.status_code == 201:
            data = response.json()
            self.document_ids.append(data["id"])
    
    @task(3)
    def extract_clauses(self):
        """Extract clauses."""
        if not self.document_ids:
            return
        
        doc_id = random.choice(self.document_ids)
        self.client.post(
            f"/api/v1/documents/{doc_id}/extract-clauses",
            headers=self.headers,
            name="/documents/{id}/extract-clauses",
        )
    
    @task(2)
    def create_exports(self):
        """Create exports."""
        if not self.document_ids:
            return
        
        doc_id = random.choice(self.document_ids)
        self.client.post(
            "/api/v1/exports",
            json={
                "document_id": doc_id,
                "export_type": "summary",
                "file_format": "pdf",
            },
            headers=self.headers,
            name="/exports [create]",
        )


# Performance test event handlers for reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Print test start message."""
    print("\n" + "="*60)
    print("LEGALLENS PERFORMANCE TEST STARTING")
    print("="*60)
    print(f"Target: 100 concurrent users")
    print(f"Expected P95 latency: <2s (reads), <5s (writes)")
    print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print test summary."""
    print("\n" + "="*60)
    print("LEGALLENS PERFORMANCE TEST COMPLETE")
    print("="*60)
    
    stats = environment.stats
    
    print("\nAGGREGATE STATISTICS:")
    print(f"  Total Requests: {stats.total.num_requests}")
    print(f"  Total Failures: {stats.total.num_failures}")
    print(f"  Failure Rate: {stats.total.fail_ratio:.2%}")
    print(f"  Median Response Time: {stats.total.median_response_time}ms")
    print(f"  95th Percentile: {stats.total.get_response_time_percentile(0.95)}ms")
    print(f"  99th Percentile: {stats.total.get_response_time_percentile(0.99)}ms")
    print(f"  Requests/sec: {stats.total.total_rps:.2f}")
    
    print("\nTOP ENDPOINTS BY REQUEST COUNT:")
    sorted_stats = sorted(
        stats.entries.values(),
        key=lambda x: x.num_requests,
        reverse=True
    )[:5]
    
    for stat in sorted_stats:
        print(f"  {stat.name}: {stat.num_requests} requests, "
              f"P95={stat.get_response_time_percentile(0.95)}ms")
    
    print("\n" + "="*60)
