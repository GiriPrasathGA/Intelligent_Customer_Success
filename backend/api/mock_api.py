"""
NovaCart — Mock REST API Endpoints

Provides realistic mock data for all NovaCart business entities with real consumer brands.
These endpoints simulate a real e-commerce backend.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends

from backend.config.models import (
    Product, Order, TrackOrderRequest, ReturnRequest,
    RefundRequest, SupportTicket, FAQItem
)
from backend.auth import get_current_user
from backend.database import User

router = APIRouter(prefix="/api/mock", tags=["Mock Data APIs"])


# ── Mock Data with Real-World Consumer Brands ─────────────────────────────────

MOCK_PRODUCTS: list[dict] = [
    {
        "id": "YC-PRD-001",
        "name": "Apple iPhone 15 Pro",
        "category": "Smartphones",
        "brand": "Apple",
        "price": 129900.0,
        "original_price": 134900.0,
        "discount_percent": 4,
        "availability": "in_stock",
        "rating": 4.9,
        "review_count": 4820,
        "description": "Grade 5 Titanium design with A17 Pro Chip, 48MP Pro camera, and Action Button",
        "specifications": {
            "display": "6.1\" Super Retina XDR OLED 120Hz ProMotion",
            "processor": "Apple A17 Pro (3nm)",
            "ram": "8GB Unified",
            "storage": "256GB NVMe",
            "battery": "3274mAh, 27W Fast Charge, MagSafe Wireless",
            "camera": "48MP Main + 12MP Ultra-wide + 12MP 3x Telephoto",
            "os": "iOS 17",
        },
        "warranty_months": 12,
    },
    {
        "id": "YC-PRD-002",
        "name": "Samsung Galaxy S24 Ultra",
        "category": "Smartphones",
        "brand": "Samsung",
        "price": 129999.0,
        "original_price": 139999.0,
        "discount_percent": 7,
        "availability": "in_stock",
        "rating": 4.8,
        "review_count": 3940,
        "description": "Ultimate Galaxy AI flagship with 200MP Quad Telephoto and built-in S-Pen",
        "specifications": {
            "display": "6.8\" Dynamic AMOLED 2X QHD+ 120Hz LTPO",
            "processor": "Snapdragon 8 Gen 3 for Galaxy (4nm)",
            "ram": "12GB LPDDR5X",
            "storage": "256GB UFS 4.0",
            "battery": "5000mAh, 45W Fast Charging",
            "camera": "200MP + 50MP 5x Periscope + 10MP 3x + 12MP UW",
            "os": "One UI 6.1 (Android 14)",
        },
        "warranty_months": 12,
    },
    {
        "id": "YC-PRD-003",
        "name": "OnePlus 12",
        "category": "Smartphones",
        "brand": "OnePlus",
        "price": 64999.0,
        "original_price": 69999.0,
        "discount_percent": 7,
        "availability": "in_stock",
        "rating": 4.7,
        "review_count": 2810,
        "description": "Smooth Beyond Belief with 2K 120Hz ProXDR and 100W SUPERVOOC charging",
        "specifications": {
            "display": "6.82\" 2K 120Hz LTPO AMOLED 4500 nits",
            "processor": "Snapdragon 8 Gen 3 (4nm)",
            "ram": "16GB LPDDR5X",
            "storage": "512GB UFS 4.0",
            "battery": "5400mAh, 100W Wired + 50W Wireless",
            "camera": "50MP Sony LYT-808 + 64MP 3x Periscope + 48MP UW",
            "os": "OxygenOS 14 (Android 14)",
        },
        "warranty_months": 12,
    },
    {
        "id": "YC-PRD-004",
        "name": "Motorola Edge 50 Pro",
        "category": "Smartphones",
        "brand": "Motorola",
        "price": 29999.0,
        "original_price": 35999.0,
        "discount_percent": 16,
        "availability": "in_stock",
        "rating": 4.6,
        "review_count": 2150,
        "description": "World's 1st Pantone Validated 1.5K 144Hz 3D curved pOLED with 125W TurboPower",
        "specifications": {
            "display": "6.7\" 1.5K 144Hz Curved pOLED 2000 nits",
            "processor": "Snapdragon 7 Gen 3 (4nm)",
            "ram": "12GB LPDDR4X",
            "storage": "256GB UFS 2.2",
            "battery": "4500mAh, 125W TurboPower (100% in 18 mins)",
            "camera": "50MP (f/1.4 OIS) + 13MP Macro + 10MP 3x Telephoto",
            "os": "Hello UI (Android 14)",
        },
        "warranty_months": 12,
    },
    {
        "id": "YC-PRD-005",
        "name": "Apple MacBook Air M3",
        "category": "Laptops",
        "brand": "Apple",
        "price": 114900.0,
        "original_price": 119900.0,
        "discount_percent": 4,
        "availability": "in_stock",
        "rating": 4.9,
        "review_count": 3120,
        "description": "Impossibly thin and incredibly fast with Apple M3 chip and 18-hour battery",
        "specifications": {
            "display": "13.6\" Liquid Retina 2560x1664 True Tone",
            "processor": "Apple M3 (8-core CPU, 10-core GPU)",
            "ram": "8GB Unified Memory",
            "storage": "256GB SSD",
            "battery": "52.6Wh, 30W USB-C MagSafe 3 (18hr life)",
            "os": "macOS Sonoma",
        },
        "warranty_months": 12,
    },
    {
        "id": "YC-PRD-006",
        "name": "Dell XPS 15",
        "category": "Laptops",
        "brand": "Dell",
        "price": 189990.0,
        "original_price": 204990.0,
        "discount_percent": 7,
        "availability": "in_stock",
        "rating": 4.8,
        "review_count": 1420,
        "description": "Premium 15.6-inch 3.5K OLED laptop with 13th Gen Intel i7 and RTX 4060",
        "specifications": {
            "display": "15.6\" 3.5K OLED Touch 400 nits",
            "processor": "Intel Core i7-13700H (14 cores, 5.0GHz)",
            "ram": "16GB DDR5 4800MHz",
            "storage": "1TB M.2 PCIe Gen 4 SSD",
            "gpu": "NVIDIA GeForce RTX 4060 8GB GDDR6",
            "battery": "86Wh, 130W Type-C AC Adapter",
            "os": "Windows 11 Home",
        },
        "warranty_months": 24,
    },
    {
        "id": "YC-PRD-007",
        "name": "Sony WH-1000XM5",
        "category": "Headphones",
        "brand": "Sony",
        "price": 29990.0,
        "original_price": 34990.0,
        "discount_percent": 14,
        "availability": "in_stock",
        "rating": 4.8,
        "review_count": 7820,
        "description": "Industry-leading wireless noise cancelling over-ear headphones with LDAC Hi-Res audio",
        "specifications": {
            "type": "Over-Ear Wireless ANC",
            "anc": "Dual QN1 + V1 processors with 8 microphones",
            "battery": "30hr (ANC on), 40hr (ANC off)",
            "bluetooth": "5.2, LDAC, AAC, SBC, Multipoint",
            "features": "Speak-to-Chat, Wear Detection, Quick Charge",
        },
        "warranty_months": 12,
    },
    {
        "id": "YC-PRD-008",
        "name": "Apple AirPods Pro (2nd Generation)",
        "category": "Headphones",
        "brand": "Apple",
        "price": 24900.0,
        "original_price": 26900.0,
        "discount_percent": 7,
        "availability": "in_stock",
        "rating": 4.9,
        "review_count": 9410,
        "description": "Magic like you've never heard with H2 chip, 2x more Active Noise Cancellation, and USB-C",
        "specifications": {
            "type": "In-Ear True Wireless ANC",
            "chip": "Apple H2 Headphone Chip",
            "battery": "6hr buds + 24hr case = 30hr total",
            "features": "Adaptive Audio, Personalized Spatial Audio, USB-C MagSafe Case",
        },
        "warranty_months": 12,
    },
    {
        "id": "YC-PRD-009",
        "name": "Boat Airdopes 141",
        "category": "Headphones",
        "brand": "Boat",
        "price": 1299.0,
        "original_price": 4490.0,
        "discount_percent": 71,
        "availability": "in_stock",
        "rating": 4.4,
        "review_count": 25410,
        "description": "Best-selling wireless earbuds with 42H playtime, Beast Mode gaming latency, and ENx noise cancelling",
        "specifications": {
            "type": "In-Ear TWS",
            "battery": "42 Hours Playback with ASAP Charge",
            "bluetooth": "5.1 with IWP Technology",
            "protection": "IPX4 Water Resistance",
        },
        "warranty_months": 12,
    },
    {
        "id": "YC-PRD-010",
        "name": "Apple Watch Series 9",
        "category": "Smart Watches",
        "brand": "Apple",
        "price": 44900.0,
        "original_price": 46900.0,
        "discount_percent": 4,
        "availability": "in_stock",
        "rating": 4.8,
        "review_count": 3120,
        "description": "Smarter, brighter, and mightier with S9 chip, Double Tap gesture, and Always-On Retina",
        "specifications": {
            "display": "45mm Always-On OLED Retina (2000 nits)",
            "processor": "Apple S9 SiP 64-bit dual-core",
            "sensors": "ECG, Blood Oxygen, Temperature Sensing, Crash Detection",
            "water_resistance": "50m swimproof",
        },
        "warranty_months": 12,
    },
    {
        "id": "YC-PRD-011",
        "name": "Sony Bravia XR 65\" 4K OLED TV",
        "category": "Televisions",
        "brand": "Sony",
        "price": 219990.0,
        "original_price": 249990.0,
        "discount_percent": 12,
        "availability": "in_stock",
        "rating": 4.9,
        "review_count": 860,
        "description": "Flagship 65-inch 4K HDR Google OLED TV with Cognitive Processor XR and Acoustic Surface Audio+",
        "specifications": {
            "display": "65\" 4K UHD (3840x2160) 120Hz OLED",
            "processor": "Cognitive Processor XR with XR Triluminos Pro",
            "audio": "Acoustic Surface Audio+ 50W Dolby Atmos",
            "gaming": "4K 120Hz, HDMI 2.1, VRR, ALLM, PS5 Auto HDR",
        },
        "warranty_months": 36,
    },
]

MOCK_ORDERS: list[dict] = [
    {
        "id": "YC-2024-001234",
        "status": "delivered",
        "items": [{"product": "Apple iPhone 15 Pro", "qty": 1, "price": 129900}],
        "total_amount": 129900.0,
        "shipping_address": "123 Main St, Mumbai, Maharashtra 400001",
        "tracking_number": "DL1234567890IN",
        "estimated_delivery": None,
        "created_at": (datetime.utcnow() - timedelta(days=15)).isoformat(),
        "updated_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
    },
    {
        "id": "YC-2024-005678",
        "status": "in_transit",
        "items": [{"product": "Sony WH-1000XM5", "qty": 1, "price": 29990}],
        "total_amount": 29990.0,
        "shipping_address": "456 Park Ave, Delhi 110001",
        "tracking_number": "BD9876543210IN",
        "estimated_delivery": (datetime.utcnow() + timedelta(days=2)).isoformat(),
        "created_at": (datetime.utcnow() - timedelta(days=3)).isoformat(),
        "updated_at": (datetime.utcnow() - timedelta(days=1)).isoformat(),
    },
    {
        "id": "YC-2024-009999",
        "status": "processing",
        "items": [{"product": "Apple MacBook Air M3", "qty": 1, "price": 114900}],
        "total_amount": 114900.0,
        "shipping_address": "789 Tech Park, Bangalore 560001",
        "tracking_number": None,
        "estimated_delivery": (datetime.utcnow() + timedelta(days=5)).isoformat(),
        "created_at": (datetime.utcnow() - timedelta(hours=6)).isoformat(),
        "updated_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
    },
]

MOCK_FAQS: list[dict] = [
    {"id": 1, "question": "How do I track my order?", "answer": "Track at novacart.com/track using your Order ID. You also receive a tracking link via email after dispatch.", "category": "Orders", "helpful_count": 1247},
    {"id": 2, "question": "What is the return window?", "answer": "Electronics: 10 days, Fashion: 30 days, Appliances: 7 days. NovaCart Plus members get 30 days on all categories.", "category": "Returns", "helpful_count": 986},
    {"id": 3, "question": "How long does the refund take?", "answer": "UPI/Net Banking: 3-5 days, Credit Card: 5-7 days, NovaCart Wallet: Instant.", "category": "Refunds", "helpful_count": 1542},
    {"id": 4, "question": "Is Cash on Delivery available?", "answer": "Yes, for orders below ₹50,000 with a ₹50 convenience fee. Available based on pincode.", "category": "Payments", "helpful_count": 834},
    {"id": 5, "question": "How do I reset my password?", "answer": "Click 'Forgot Password' on login page, enter your email, and follow the reset link (valid 1 hour).", "category": "Account", "helpful_count": 2103},
    {"id": 6, "question": "What warranty do products come with?", "answer": "All products come with 100% manufacturer warranty. Extended NovaCartCare+ plans available within 30 days of purchase.", "category": "Warranty", "helpful_count": 671},
]


# ── Product Endpoints ─────────────────────────────────────────────────────────

@router.get("/products", response_model=list[dict])
async def get_products(
    category: Optional[str] = None,
    limit: int = 20,
):
    """Get product catalog with optional category filter."""
    products = MOCK_PRODUCTS
    if category:
        products = [p for p in products if p["category"].lower() == category.lower()]
    return products[:limit]


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    """Get a single product by ID."""
    for product in MOCK_PRODUCTS:
        if product["id"] == product_id:
            return product
    raise HTTPException(status_code=404, detail=f"Product {product_id} not found")


# ── Order Endpoints ───────────────────────────────────────────────────────────

@router.get("/orders")
async def get_orders(current_user: User = Depends(get_current_user)):
    """Get all orders for the authenticated user."""
    return MOCK_ORDERS


@router.get("/orders/{order_id}")
async def get_order(order_id: str, current_user: User = Depends(get_current_user)):
    """Get a specific order by ID."""
    for order in MOCK_ORDERS:
        if order["id"] == order_id:
            return order
    raise HTTPException(status_code=404, detail=f"Order {order_id} not found")


@router.post("/track-order")
async def track_order(req: TrackOrderRequest):
    """Track an order by ID (no auth required)."""
    for order in MOCK_ORDERS:
        if order["id"] == req.order_id:
            return {
                "order_id": order["id"],
                "status": order["status"],
                "tracking_number": order.get("tracking_number"),
                "estimated_delivery": order.get("estimated_delivery"),
                "items": order["items"],
                "carrier": "Blue Dart Express" if order.get("tracking_number") else "Not yet dispatched",
                "tracking_url": f"https://www.bluedart.com/tracking/{order.get('tracking_number', '')}" if order.get("tracking_number") else None,
            }
    raise HTTPException(status_code=404, detail="Order not found. Please check your order ID.")


@router.post("/cancel-order")
async def cancel_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
):
    """Cancel an order (demo — always succeeds for processing orders)."""
    for order in MOCK_ORDERS:
        if order["id"] == order_id:
            if order["status"] in ("delivered", "cancelled"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot cancel order with status: {order['status']}"
                )
            return {
                "success": True,
                "order_id": order_id,
                "message": "Order cancellation request submitted. Refund will be processed within 5-7 business days.",
                "refund_amount": order["total_amount"],
            }
    raise HTTPException(status_code=404, detail="Order not found")


# ── Return & Refund Endpoints ─────────────────────────────────────────────────

@router.post("/return-request")
async def create_return_request(
    req: ReturnRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a return request for an order item."""
    ticket_id = f"RTN-{uuid.uuid4().hex[:8].upper()}"
    return {
        "success": True,
        "return_ticket_id": ticket_id,
        "order_id": req.order_id,
        "status": "initiated",
        "pickup_scheduled": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "message": f"Return request created (Ref: {ticket_id}). Pickup scheduled within 24-48 hours.",
    }


@router.post("/refund-request")
async def create_refund_request(
    req: RefundRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a refund request."""
    ref_id = f"RFD-{uuid.uuid4().hex[:8].upper()}"
    return {
        "success": True,
        "refund_reference": ref_id,
        "order_id": req.order_id,
        "amount": req.amount,
        "status": "initiated",
        "estimated_credit": "3-7 business days to original payment method",
        "message": f"Refund initiated (Ref: {ref_id}). You'll receive a confirmation email.",
    }


# ── Warranty & Support Endpoints ──────────────────────────────────────────────

@router.get("/warranty")
async def get_warranty_info(
    product_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Get warranty information for a product."""
    return {
        "standard_warranty": "12 months manufacturer warranty (Brand Authorized Service)",
        "extended_plans": [
            {"name": "NovaCartCare+ 1 Year", "price_range": "₹999 - ₹2,999", "coverage": "1 additional year + 1 accidental damage"},
            {"name": "NovaCartCare+ 2 Year", "price_range": "₹1,999 - ₹5,999", "coverage": "2 additional years + 2 accidental damage"},
            {"name": "NovaCartCare+ Comprehensive", "price_range": "₹2,999 - ₹8,999", "coverage": "2 additional years + unlimited accidental damage"},
        ],
        "service_centers": "novacart.com/service-centers",
        "support_number": "1800-NOVACART-HELP",
    }


@router.post("/create-ticket")
async def create_support_ticket(
    ticket: SupportTicket,
    current_user: User = Depends(get_current_user),
):
    """Create a customer support ticket."""
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    return {
        "success": True,
        "ticket_id": ticket_id,
        "status": "open",
        "priority": ticket.priority,
        "expected_response": "Within 24 hours",
        "message": f"Support ticket created (ID: {ticket_id}). Our team will contact you within 24 hours.",
    }


@router.post("/reset-password")
async def mock_reset_password(email: str):
    """Demo password reset endpoint."""
    return {
        "success": True,
        "message": "Password reset link sent to your registered email address.",
        "expires_in": "1 hour",
    }


@router.get("/faq")
async def get_faqs(category: Optional[str] = None):
    """Get FAQ list with optional category filter."""
    faqs = MOCK_FAQS
    if category:
        faqs = [f for f in faqs if f["category"].lower() == category.lower()]
    return faqs

