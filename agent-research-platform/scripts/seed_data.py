#!/usr/bin/env python
"""Seed database with realistic B2B demo data."""

import asyncio
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from faker import Faker

from research_platform.db.embeddings import EmbeddingService
from research_platform.db.models import (
    Customer,
    Document,
    Order,
    OrderItem,
    Organization,
    Product,
    SupportTicket,
    TicketMessage,
    User,
)
from research_platform.db.session import get_session

fake = Faker()


async def seed_organizations(count: int = 3) -> list[Organization]:
    """Create demo organizations."""
    print(f"Creating {count} organizations...")

    orgs = [
        Organization(
            name=fake.company(),
            tier=random.choice(["free", "pro", "enterprise"]),
            is_active=True,
        )
        for _ in range(count)
    ]

    async with get_session() as session:
        session.add_all(orgs)
        await session.flush()
        await session.refresh(orgs[0])  # Refresh to get IDs

    print(f"✓ Created {count} organizations")
    return orgs


async def seed_users(orgs: list[Organization]) -> list[User]:
    """Create demo users."""
    print("Creating users...")

    users = []
    for org in orgs:
        # 3-7 users per org
        for _ in range(random.randint(3, 7)):
            users.append(
                User(
                    organization_id=org.id,
                    email=fake.email(),
                    name=fake.name(),
                    role=random.choice(["admin", "member", "member", "viewer"]),
                    is_active=True,
                )
            )

    async with get_session() as session:
        session.add_all(users)

    print(f"✓ Created {len(users)} users")
    return users


async def seed_products(orgs: list[Organization], embeddings: EmbeddingService) -> list[Product]:
    """Create demo products with embeddings."""
    print("Creating products with embeddings...")

    product_categories = {
        "Software": [
            ("Enterprise CRM Platform", "Complete customer relationship management solution with AI-powered insights"),
            ("Project Management Suite", "Collaborative project tracking and resource management software"),
            ("Business Intelligence Dashboard", "Real-time analytics and reporting platform for data-driven decisions"),
            ("Email Marketing Automation", "Advanced email campaign management with personalization and A/B testing"),
            ("HR Management System", "Comprehensive employee management, payroll, and benefits administration"),
        ],
        "Hardware": [
            ("Cloud Server Rack", "High-performance 42U server rack with redundant power and cooling"),
            ("Enterprise Router", "Multi-gigabit routing solution with advanced security features"),
            ("Backup Storage Array", "Petabyte-scale storage with automatic failover and encryption"),
            ("Video Conferencing System", "4K video conferencing with AI noise cancellation"),
        ],
        "Services": [
            ("Cloud Hosting - Enterprise", "Managed cloud hosting with 99.99% uptime SLA"),
            ("Cybersecurity Audit", "Comprehensive security assessment and penetration testing"),
            ("Data Migration Service", "Expert-led data migration with zero downtime guarantee"),
            ("24/7 Technical Support", "Premium support with dedicated account manager"),
        ],
    }

    products = []
    product_texts = []

    for org in orgs:
        for category, items in product_categories.items():
            for name, description in items:
                products.append(
                    Product(
                        organization_id=org.id,
                        name=name,
                        description=description,
                        category=category,
                        price=round(random.uniform(99, 9999), 2),
                        sku=f"{category[:3].upper()}-{fake.ean8()}",
                        is_active=True,
                    )
                )
                # Combine name and description for embedding
                product_texts.append(f"{name}. {description}")

    # Generate embeddings in batch
    print("Generating embeddings for products...")
    embeddings_list = await embeddings.embed_batch(product_texts)

    for product, embedding in zip(products, embeddings_list):
        product.embedding = embedding

    async with get_session() as session:
        session.add_all(products)

    print(f"✓ Created {len(products)} products with embeddings")
    return products


async def seed_customers(orgs: list[Organization]) -> list[Customer]:
    """Create demo customers."""
    print("Creating customers...")

    customers = []
    for org in orgs:
        # 10-20 customers per org
        for _ in range(random.randint(10, 20)):
            customers.append(
                Customer(
                    organization_id=org.id,
                    company_name=fake.company(),
                    contact_email=fake.company_email(),
                    contact_name=fake.name(),
                    tier=random.choice(["standard", "premium", "vip"]),
                    is_active=True,
                )
            )

    async with get_session() as session:
        session.add_all(customers)

    print(f"✓ Created {len(customers)} customers")
    return customers


async def seed_orders(customers: list[Customer], products: list[Product]) -> list[Order]:
    """Create demo orders."""
    print("Creating orders...")

    orders = []
    order_items = []

    for customer in customers:
        # 0-5 orders per customer
        num_orders = random.randint(0, 5)

        for i in range(num_orders):
            order_date = datetime.now() - timedelta(days=random.randint(0, 365))

            order = Order(
                customer_id=customer.id,
                order_number=f"ORD-{fake.ean13()}",
                status=random.choice(
                    ["pending", "processing", "shipped", "delivered", "delivered", "delivered"]
                ),
                total_amount=0,  # Will calculate below
                created_at=order_date,
            )
            orders.append(order)

            # 1-5 items per order
            order_total = 0
            customer_products = [p for p in products if p.organization_id == customer.organization_id]

            for _ in range(random.randint(1, 5)):
                product = random.choice(customer_products)
                quantity = random.randint(1, 10)
                unit_price = product.price
                total_price = quantity * unit_price

                order_items.append(
                    OrderItem(
                        order=order,
                        product_id=product.id,
                        quantity=quantity,
                        unit_price=unit_price,
                        total_price=total_price,
                    )
                )

                order_total += total_price

            order.total_amount = order_total

    async with get_session() as session:
        session.add_all(orders)
        session.add_all(order_items)

    print(f"✓ Created {len(orders)} orders with {len(order_items)} items")
    return orders


async def seed_support_tickets(
    customers: list[Customer], embeddings: EmbeddingService
) -> list[SupportTicket]:
    """Create demo support tickets with embeddings."""
    print("Creating support tickets with embeddings...")

    ticket_subjects = [
        "Unable to login to account",
        "Order not received",
        "Request for refund",
        "Product quality issue",
        "Billing discrepancy",
        "Feature request: API access",
        "Integration with third-party software",
        "Performance issues with dashboard",
        "Need help configuring settings",
        "Account upgrade inquiry",
    ]

    tickets = []
    messages = []
    ticket_texts = []

    for customer in customers:
        # 0-3 tickets per customer
        for _ in range(random.randint(0, 3)):
            subject = random.choice(ticket_subjects)
            created_date = datetime.now() - timedelta(days=random.randint(0, 90))

            ticket = SupportTicket(
                customer_id=customer.id,
                ticket_number=f"TKT-{fake.ean8()}",
                subject=subject,
                status=random.choice(["open", "in_progress", "resolved", "closed"]),
                priority=random.choice(["low", "medium", "high", "urgent"]),
                sentiment_score=random.uniform(-1, 1),
                created_at=created_date,
            )
            tickets.append(ticket)

            # First message from customer
            first_message = fake.paragraph(nb_sentences=3)
            messages.append(
                TicketMessage(
                    ticket=ticket,
                    sender_type="customer",
                    sender_name=customer.contact_name,
                    message=first_message,
                    created_at=created_date,
                )
            )

            # Combine subject and first message for embedding
            ticket_texts.append(f"{subject}. {first_message}")

            # Agent response
            if random.random() > 0.3:
                messages.append(
                    TicketMessage(
                        ticket=ticket,
                        sender_type="agent",
                        sender_name="Support Agent",
                        message=fake.paragraph(nb_sentences=2),
                        created_at=created_date + timedelta(hours=random.randint(1, 48)),
                    )
                )

    # Generate embeddings for tickets
    print("Generating embeddings for tickets...")
    embeddings_list = await embeddings.embed_batch(ticket_texts)

    for ticket, embedding in zip(tickets, embeddings_list):
        ticket.embedding = embedding

    async with get_session() as session:
        session.add_all(tickets)
        session.add_all(messages)

    print(f"✓ Created {len(tickets)} support tickets with {len(messages)} messages")
    return tickets


async def seed_documents(orgs: list[Organization], embeddings: EmbeddingService) -> list[Document]:
    """Create demo documents with embeddings."""
    print("Creating documents with embeddings...")

    doc_templates = [
        ("Getting Started Guide", "Learn how to set up your account and configure basic settings. This comprehensive guide covers account creation, team member invitations, and initial setup steps.", "article"),
        ("API Documentation", "Complete API reference with authentication, endpoints, rate limits, and code examples in multiple programming languages.", "article"),
        ("Pricing and Plans", "Compare our pricing tiers and features. Enterprise plans include dedicated support, custom integrations, and volume discounts.", "faq"),
        ("Data Security Policy", "Our commitment to data security includes SOC 2 compliance, encryption at rest and in transit, and regular security audits.", "policy"),
        ("Return and Refund Policy", "Products can be returned within 30 days for a full refund. Contact support to initiate a return.", "policy"),
        ("Troubleshooting Common Issues", "Solutions for login problems, payment failures, and integration errors. Check here before contacting support.", "faq"),
        ("Advanced Features Tutorial", "Unlock the full potential with custom workflows, automation rules, and advanced reporting capabilities.", "article"),
        ("System Requirements", "Minimum and recommended system requirements for optimal performance. Compatible with Windows, macOS, and Linux.", "manual"),
        ("Privacy Policy", "We respect your privacy and comply with GDPR, CCPA, and other data protection regulations.", "policy"),
        ("Integration Guide", "Step-by-step instructions for integrating with Salesforce, Slack, Microsoft Teams, and other popular platforms.", "manual"),
    ]

    documents = []
    doc_texts = []

    for org in orgs:
        for title, content, doc_type in doc_templates:
            full_content = f"{content} {fake.paragraph(nb_sentences=5)}"

            documents.append(
                Document(
                    organization_id=org.id,
                    title=title,
                    content=full_content,
                    document_type=doc_type,
                    tags={"category": doc_type, "featured": random.choice([True, False])},
                )
            )

            # Combine title and content for embedding
            doc_texts.append(f"{title}. {full_content}")

    # Generate embeddings
    print("Generating embeddings for documents...")
    embeddings_list = await embeddings.embed_batch(doc_texts)

    for doc, embedding in zip(documents, embeddings_list):
        doc.embedding = embedding

    async with get_session() as session:
        session.add_all(documents)

    print(f"✓ Created {len(documents)} documents with embeddings")
    return documents


async def main():
    """Seed all demo data."""
    print("=== Seeding Demo Data ===\n")

    try:
        embeddings = EmbeddingService()

        # Seed in order (respecting foreign keys)
        orgs = await seed_organizations(count=2)
        await seed_users(orgs)
        products = await seed_products(orgs, embeddings)
        customers = await seed_customers(orgs)
        await seed_orders(customers, products)
        await seed_support_tickets(customers, embeddings)
        await seed_documents(orgs, embeddings)

        print("\n✓ Demo data seeding complete!")
        print(f"\nCreated data for {len(orgs)} organizations")
        print("You can now run agents against this data.")

    except Exception as e:
        print(f"\n✗ Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
