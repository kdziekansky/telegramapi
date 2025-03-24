# database/credits_client.py
from services.api_service import APIService
from services.repository_service import RepositoryService

# Utworzenie globalnych instancji
api_service = APIService()
repository_service = RepositoryService(api_service.supabase)

# Funkcje dla kompatybilności wstecznej
def get_user_credits(user_id):
    """Funkcja dla kompatybilności wstecznej - bez async/await"""
    try:
        # Bezpośrednie zapytanie do Supabase
        response = supabase.table('user_credits').select('credits_amount').eq('user_id', user_id).execute()
        
        if response.data:
            return response.data[0].get('credits_amount', 100)  # Domyślnie 100 kredytów
        
        # Inicjalizacja nowego użytkownika
        supabase.table('user_credits').insert({
            'user_id': user_id,
            'credits_amount': 100,  # Każdy nowy użytkownik dostaje 100 kredytów
            'total_credits_purchased': 0,
            'total_spent': 0
        }).execute()
        
        return 100  # Początkowa liczba kredytów
    except Exception as e:
        print(f"Błąd przy pobieraniu kredytów: {e}")
        return 100  # W razie błędu również zwróć 100

async def add_user_credits(user_id, amount, description=None):
    """Funkcja dla kompatybilności wstecznej"""
    return await repository_service.credit_repository.add_user_credits(user_id, amount, description)

async def deduct_user_credits(user_id, amount, description=None):
    """Funkcja dla kompatybilności wstecznej"""
    return await repository_service.credit_repository.deduct_user_credits(user_id, amount, description)

async def check_user_credits(user_id, amount_needed):
    """Funkcja dla kompatybilności wstecznej"""
    return await repository_service.credit_repository.check_user_credits(user_id, amount_needed)

async def get_credit_packages():
    """Funkcja dla kompatybilności wstecznej"""
    return await repository_service.credit_repository.get_credit_packages()

async def get_package_by_id(package_id):
    """Funkcja dla kompatybilności wstecznej"""
    return await repository_service.credit_repository.get_package_by_id(package_id)

async def purchase_credits(user_id, package_id):
    """Funkcja dla kompatybilności wstecznej"""
    return await repository_service.credit_repository.purchase_credits(user_id, package_id)

async def get_user_credit_stats(user_id):
    """Funkcja dla kompatybilności wstecznej"""
    return await repository_service.credit_repository.get_user_stats(user_id)

async def add_stars_payment_option(stars_count, credits_amount):
    """Funkcja dla kompatybilności wstecznej"""
    return await repository_service.credit_repository.add_stars_payment_option(stars_count, credits_amount)

async def get_stars_conversion_rate():
    """Funkcja dla kompatybilności wstecznej"""
    return await repository_service.credit_repository.get_stars_conversion_rate()