from app.db.seed import seed_demo_data
from app.db.session import SessionLocal


def main() -> None:
    with SessionLocal() as db:
        seed_demo_data(db)
    print("Demo seed data inserted successfully.")


if __name__ == "__main__":
    main()

