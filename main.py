import os
from datetime import datetime, timedelta

import psycopg
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext

app = FastAPI()

# ---------------- DATABASE ----------------

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "vente")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "root")

DATABASE_DSN = (
    f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"
)

# ---------------- JWT ----------------

SECRET_KEY = "SUPER_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

security = HTTPBearer()

# ---------------- PASSWORD FUNCTIONS ----------------

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(
        plain_password,
        hashed_password
    )

# ---------------- TOKEN FUNCTIONS ----------------

def create_access_token(data: dict):

    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

# ---------------- ROOT ----------------

@app.get("/")
def read_root():
    return {"Hello": "World"}

# ---------------- CREATE USER ----------------

@app.post("/user/")
def create_user(
    nom: str,
    prenom: str,
    email: str,
    password: str,
    telephone: str,
    role: str
):

    try:

        hashed_password = hash_password(password)

        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO users
                    (nom, prenom, email, password_hash, telephone, role, created_at)

                    VALUES (%s, %s, %s, %s, %s, %s, NOW())

                    RETURNING id
                    """,
                    (
                        nom,
                        prenom,
                        email,
                        hashed_password,
                        telephone,
                        role
                    )
                )

                user_id = cur.fetchone()[0]

        token = create_access_token({
            "sub": email,
            "user_id": user_id,
            "role": role
        })

        return {
            "status": "ok",
            "user_id": user_id,
            "access_token": token
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ---------------- LOGIN ----------------

@app.post("/login/")
def login(email: str, password: str):

    try:

        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT id, email, password_hash, role
                    FROM users
                    WHERE email = %s
                    """,
                    (email,)
                )

                user = cur.fetchone()

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid email"
            )

        user_id = user[0]
        user_email = user[1]
        hashed_password = user[2]
        role = user[3]

        if not verify_password(password, hashed_password):

            raise HTTPException(
                status_code=401,
                detail="Invalid password"
            )

        token = create_access_token({
            "sub": user_email,
            "user_id": user_id,
            "role": role
        })

        return {
            "access_token": token,
            "token_type": "bearer"
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ---------------- PROTECTED ROUTE ----------------

@app.get("/profile/")
def profile(user=Depends(verify_token)):

    return {
        "message": "Protected route",
        "user": user
    }

# ---------------- GET USERS ----------------

@app.get("/users/{user_id}")
def get_user(
    user_id: int,
    user=Depends(verify_token)
):

    try:

        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT id, nom, prenom, email,
                    telephone, role, created_at

                    FROM users
                    WHERE id = %s
                    """,
                    (user_id,)
                )

                result = cur.fetchone()

        if not result:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        return {
            "status": "ok",
            "user": {
                "id": result[0],
                "nom": result[1],
                "prenom": result[2],
                "email": result[3],
                "telephone": result[4],
                "role": result[5]
            }
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
@app.get("/categories/")
def get_categories():
    """Retrieve all categories."""
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nom FROM categories")
                categories = cur.fetchall()
        return {"status": "ok", "categories": [{"id": cat[0], "nom": cat[1]} for cat in categories]}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.get("/articles/")
def get_articles():
    """Retrieve all articles."""
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nom, description, prix, stock FROM articles")
                articles = cur.fetchall()
        return { "articles": [{"id": art[0], "nom": art[1], "description": art[2], "prix": float(art[3]), "stock": art[4]} for art in articles]}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.post("/panier/")
def add_to_panier(
    article_id: int,
    quantity: int,
    user=Depends(verify_token)
):
    """Add an article to the user's cart."""
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                # Check if the article exists and has enough stock
                cur.execute("SELECT quantite_stock FROM articles WHERE id = %s", (article_id,))
                result = cur.fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail="Article not found")
                if result[0] < quantity:
                    raise HTTPException(status_code=400, detail="Not enough stock")

                # Add to cart
                cur.execute(
                    """
                    INSERT INTO panier_items (user_id, article_id, quantity)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, article_id) DO UPDATE
                    SET quantity = panier.quantity + EXCLUDED.quantity
                    """,
                    (user["user_id"], article_id, quantity)
                )
        return {"status": "ok", "message": "Article added to cart"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.get("/panier/")
def view_panier(user=Depends(verify_token)):
    """View the contents of the user's cart."""
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                select * from paniers p,commande_items c,commandes cc
where c.commande_id=cc.id and  p.user_id = %s
                    """,
                    (user["user_id"],)
                )
                items = cur.fetchall()
        return {"status": "ok", "panier": [{"article_id": item[0], "nom": item[1], "prix": float(item[2]), "quantity": item[3]} for item in items]}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.get("facture/")
def generate_facture(user=Depends(verify_token)):
    """Generate an invoice for the user's cart."""
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                # Get cart items
                cur.execute(
                    """
                     select * from  factures f,commandes c
where f.commande_id=c.id and c.user_id = %s
                    """,
                    (user["user_id"],)
                )
                items = cur.fetchall()

                if not items:
                    raise HTTPException(status_code=400, detail="Cart is empty")

                # Calculate total
                total = sum(float(item[2]) * item[3] for item in items)

                # Here you would typically create an order and save it to the database

        return {"status": "ok", "facture": {"items": [{"article_id": item[0], "nom": item[1], "prix": float(item[2]), "quantity": item[3]} for item in items], "total": total}}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.post("/facture/confirm/")
def confirm_facture(user=Depends(verify_token)):
    """Confirm the invoice and create an order."""
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                # Get cart items
                cur.execute(
                    """
select * from paniers p,commande_items c,commandes cc
where c.commande_id=cc.id and  p.user_id = %s;
                    """,
                    (user["user_id"],)
                )
                items = cur.fetchall()

                if not items:
                    raise HTTPException(status_code=400, detail="Cart is empty")

                # Calculate total
                total = sum(float(item[2]) * item[3] for item in items)

                # Create order (this is just a placeholder, you would need to implement the actual order creation logic)
                cur.execute(
                    """
                    INSERT INTO orders (user_id, total, created_at)
                    VALUES (%s, %s, NOW())
                    RETURNING id
                    """,
                    (user["user_id"], total)
                )
                order_id = cur.fetchone()[0]

                # Clear cart
                cur.execute("DELETE FROM panier_items WHERE user_id = %s", (user["user_id"],))

        return {"status": "ok", "message": "Order confirmed", "order_id": order_id}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.post("commande/")
def create_commande(user=Depends(verify_token)):
    """Create an order for the user."""
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                # Get cart items
                cur.execute(
                    """
                    INSERT INTO commandes (user_id, total, statut, adresse_livraison, date_commande)
VALUES (3, 1235.21, 'en_attente', 'fghj', '2026-05-09 00:38:59.944585');
                    """
                )
                items = cur.fetchall()

                if not items:
                    raise HTTPException(status_code=400, detail="Cart is empty")

                # Calculate total
                total = sum(float(item[2]) * item[3] for item in items)

                # Create order (this is just a placeholder, you would need to implement the actual order creation logic)
                cur.execute(
                    """
                    INSERT INTO orders (user_id, total, created_at)
                    VALUES (%s, %s, NOW())
                    RETURNING id
                    """,
                    (user["user_id"], total)
                )
                order_id = cur.fetchone()[0]

                # Clear cart
                cur.execute("DELETE FROM panier_items WHERE user_id = %s", (user["user_id"],))

        return {"status": "ok", "message": "Order created", "order_id": order_id}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.get("categories/")
def get_categories():
    """Retrieve all categories."""
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM categories")
                categories = cur.fetchall()
        return {"status": "ok", "categories": [{"id": cat[0], "nom": cat[1]} for cat in categories]}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})   
@app.post("/categories/")
def create_category(nom: str, user=Depends(verify_token)):  
    """Create a new category."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO categories (nom, description)
                    VALUES (%s, NOW())
                    RETURNING id
                    """,
                    (nom,)
                )
                category_id = cur.fetchone()[0]
        return {"status": "ok", "message": "Category created", "category_id": category_id}
    except Exception as e:         
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.post("categories/{category_id}/articles/")
def create_article(category_id: int, nom: str, description: str, prix: float, stock: int, user=Depends(verify_token)):
    """Create a new article in a category."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                # Check if category exists
                cur.execute("SELECT id FROM categories WHERE id = %s", (category_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Category not found")

                # Create article
                cur.execute(
                    """
                    INSERT INTO articles (category_id,image_url, nom, description, prix, quantite_stock, marque,code_barres,seuil_alerte,reference)
                    VALUES (%s, %s, %s, %s, %s,%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (category_id,image_url, nom, description, prix, quantite_stock, marque,code_barres,seuil_alerte,reference)
                )
                article_id = cur.fetchone()[0]
        return {"status": "ok", "message": "Article created", "article_id": article_id}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.get("approvisionnements/")
def get_approvisionnements(user=Depends(verify_token)):
    """Retrieve all approvisionnements."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                     SELECT id, article_id, demandeur_id, statut, date_demande, commentaire
	FROM public.demandes_reapprovisionnement;
                    """
                )
                approvisionnements = cur.fetchall()
        return {"status": "ok", "approvisionnements": [{"id": app[0], "article_nom": app[1], "quantite": app[2], "created_at": app[3]} for app in approvisionnements]}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.post("/approvisionnements/")
def create_approvisionnement(article_id: int, quantite: int, user=Depends(verify_token)):
    """Create a new approvisionnement."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                # Check if article exists
                cur.execute("SELECT id FROM articles WHERE id = %s", (article_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Article not found")

                # Create approvisionnement
                cur.execute(
                    """
                    INSERT INTO public.demandes_reapprovisionnement(
	id, article_id, demandeur_id, statut, date_demande, commentaire)
	VALUES (%s,%s , %s, %s, %s, %s);
                    """,
                    (article_id, quantite)
                )
                approvisionnement_id = cur.fetchone()[0]

                # Update article stock
                cur.execute(
                    """
                    UPDATE articles
                    SET quantite_stock = quantite_stock + %s
                    WHERE id = %s
                    """,
                    (quantite, article_id)
                )
        return {"status": "ok", "message": "Approvisionnement created", "approvisionnement_id": approvisionnement_id}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.post("users/")
def create_user(
    nom: str,
    prenom: str,
    email: str,
    password: str,
    telephone: str,
    role: str
):
    """Create a new user."""
    try:
        hashed_password = hash_password(password)
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (nom, prenom, email, password_hash, telephone, role, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id
                    """,
                    (nom, prenom, email, hashed_password, telephone, role)
                )
                user_id = cur.fetchone()[0]
        token = create_access_token({"sub": email, "user_id": user_id, "role": role})
        return {"status": "ok", "user_id": user_id, "access_token": token}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})
@app.get("users")
def get_users(user=Depends(verify_token)):
    """Retrieve all users."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        with psycopg.connect(DATABASE_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nom, prenom, email, telephone, role FROM users")
                users = cur.fetchall()
        return {"status": "ok", "users": [{"id": usr[0], "nom": usr[1], "prenom": usr[2], "email": usr[3], "telephone": usr[4], "role": usr[5]} for usr in users]}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "error", "error": str(e)})