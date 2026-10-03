import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

def generate_uuid():
    return uuid.uuid4()

def utc_now():
    return datetime.now(timezone.utc)

class Show(Base):
    __tablename__ = 'shows'

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    price_paise = Column(BigInteger, nullable=False)
    per_user_limit = Column(Integer, nullable=False, default=4)
    total_seats = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class Seat(Base):
    __tablename__ = 'seats'

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    show_id = Column(UUID(as_uuid=True), ForeignKey('shows.id'), nullable=False)
    seat_number = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default='available')

    __table_args__ = (
        UniqueConstraint('show_id', 'seat_number', name='uix_show_seat'),
    )


class Reservation(Base):
    __tablename__ = 'reservations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    show_id = Column(UUID(as_uuid=True), ForeignKey('shows.id'), nullable=False)
    user_id = Column(String(255), nullable=False)
    idempotency_key = Column(String(255), nullable=False)
    request_hash = Column(String(64), nullable=False)
    amount_paise = Column(BigInteger, nullable=False)
    status = Column(String(20), nullable=False, default='confirmed')
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint('show_id', 'user_id', 'idempotency_key', name='uix_show_user_idempotency'),
    )


class ReservationSeat(Base):
    __tablename__ = 'reservation_seats'

    reservation_id = Column(UUID(as_uuid=True), ForeignKey('reservations.id'), primary_key=True)
    seat_id = Column(UUID(as_uuid=True), ForeignKey('seats.id'), primary_key=True)


class UserShowBookingState(Base):
    __tablename__ = 'user_show_booking_state'

    show_id = Column(UUID(as_uuid=True), ForeignKey('shows.id'), primary_key=True)
    user_id = Column(String(255), primary_key=True)
    active_seat_count = Column(Integer, nullable=False, default=0)
