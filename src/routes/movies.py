from typing import Optional, Literal
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy import select, or_, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models.orders import OrderItem
from src.database.session import get_db
from src.database.models.movies import (
    Movie,
    Certification,
    Genre,
    Star,
    Director,
)
from src.schemas.movies import (
    MovieListResponseSchema,
    MovieListItemSchema,
    MovieCreateSchema,
    MovieDetailSchema,
    MovieUpdateSchema,
)
from src.security.auth_dependencies import moderator_required

router = APIRouter()


@router.get(
    "/",
    response_model=MovieListResponseSchema,
    summary="Retrieve all movies",
    description="Returns a paginated list of movies "
    "with optional filtering, sorting, "
    "and search capabilities.",
    status_code=status.HTTP_200_OK,
)
async def get_movie_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_db),
    year: Optional[int] = Query(None, description="Filter by year"),
    imdb: Optional[float] = Query(None, description="Filter by imdb rating"),
    sort_by: Literal["id", "price", "time", "votes"] = Query("id"),
    order: Literal["asc", "desc"] = Query("asc"),
    search: Optional[str] = Query(
        None, description="Filter by name, description, stars and directors"
    ),
) -> MovieListResponseSchema:
    query = select(Movie)

    # filters
    if year is not None:
        query = query.where(Movie.year == year)
    if imdb is not None:
        query = query.where(Movie.imdb == imdb)

    # sorting
    if not hasattr(Movie, sort_by):
        raise HTTPException(status_code=422, detail=f"Invalid sort field: {sort_by}")
    column = getattr(Movie, sort_by)
    query = query.order_by(column.desc() if order == "desc" else column)

    # search
    if search:
        query = query.where(
            or_(
                Movie.name.ilike(f"%{search}%"),
                Movie.description.ilike(f"%{search}%"),
                Movie.stars.any(Star.name.ilike(f"%{search}%")),
                Movie.directors.any(Director.name.ilike(f"%{search}%")),
            )
        )

    # total count
    total_items_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total_items = total_items_result.scalar() or 0
    total_pages = (total_items + per_page - 1) // per_page

    if total_pages == 0 or page > total_pages:
        raise HTTPException(
            status_code=404, detail="No movies found matching the specified criteria"
        )

    # pagination
    offset = (page - 1) * per_page
    result = await db.execute(query.offset(offset).limit(per_page))
    movies = result.scalars().all()

    if not movies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No movies found matching the specified criteria",
        )

    movie_list = [MovieListItemSchema.model_validate(movie) for movie in movies]

    return MovieListResponseSchema(
        movies=movie_list,
        prev_page=(
            f"/movies/?page={page - 1}&per_page={per_page}"
            f"&sort_by={sort_by}&order={order}"
            if page > 1
            else None
        ),
        next_page=(
            f"/movies/?page={page + 1}&per_page={per_page}"
            f"&sort_by={sort_by}&order={order}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )


@router.get(
    "/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get movie detail by ID",
    description="Retrieves detailed information about "
    "a specific movie including its "
    "certification, genres, stars, and directors.",
    status_code=status.HTTP_200_OK,
)
async def get_movie_by_id(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    stmt = (
        select(Movie)
        .options(
            joinedload(Movie.certification),
            joinedload(Movie.genres),
            joinedload(Movie.stars),
            joinedload(Movie.directors),
        )
        .where(Movie.id == movie_id)
    )

    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with ID '{movie_id}' not found.",
        )

    return MovieDetailSchema.model_validate(movie)


@router.post(
    "/",
    response_model=MovieDetailSchema,
    summary="Create a new movie record",
    description=(
        "Add a new movie to the database, including "
        "its genres, stars, directors, "
        "and certification. If any of the related "
        "entities don’t exist, they’ll be created automatically."
    ),
    status_code=status.HTTP_201_CREATED,
)
async def create_movie(
    movie_data: MovieCreateSchema,
    current_user=Depends(moderator_required),
    db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    existing_stmt = select(Movie).where(
        (Movie.name == movie_data.name), (Movie.time == movie_data.time)
    )
    existing_result = await db.execute(existing_stmt)
    existing_movie = existing_result.scalars().first()

    if existing_movie:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"The movie '{movie_data.name}' released on "
                f"'{movie_data.time}' already exists in the database."
            ),
        )

    try:
        # certification
        certification_stmt = select(Certification).where(
            Certification.name == movie_data.certification
        )
        certification_result = await db.execute(certification_stmt)
        certification = certification_result.scalars().first()
        if not certification:
            certification = Certification(name=movie_data.certification)
            db.add(certification)
            await db.flush()

        # genres
        genres = []
        for genre_name in movie_data.genres:
            genre_stmt = select(Genre).where(Genre.name == genre_name)
            genre_result = await db.execute(genre_stmt)
            genre = genre_result.scalars().first()
            if not genre:
                genre = Genre(name=genre_name)
                db.add(genre)
                await db.flush()
            genres.append(genre)

        # stars
        stars = []
        for star_name in movie_data.stars:
            star_stmt = select(Star).where(Star.name == star_name)
            star_result = await db.execute(star_stmt)
            star = star_result.scalars().first()
            if not star:
                star = Star(name=star_name)
                db.add(star)
                await db.flush()
            stars.append(star)

        # directors
        directors = []
        for director_name in movie_data.directors:
            director_stmt = select(Director).where(Director.name == director_name)
            director_result = await db.execute(director_stmt)
            director = director_result.scalars().first()
            if not director:
                director = Director(name=director_name)
                db.add(director)
                await db.flush()
            directors.append(director)

        # movie
        movie = Movie(
            name=movie_data.name,
            year=movie_data.year,
            time=movie_data.time,
            imdb=movie_data.imdb,
            votes=movie_data.votes,
            meta_score=movie_data.meta_score,
            gross=movie_data.gross,
            description=movie_data.description,
            price=movie_data.price,
            certification=certification,
            genres=genres,
            stars=stars,
            directors=directors,
        )
        db.add(movie)
        await db.commit()
        await db.refresh(movie, ["genres", "stars", "directors"])

        return MovieDetailSchema.model_validate(movie)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid movie data. Please check your input and try again.",
        )


@router.patch(
    "/{movie_id}",
    summary="Update a movie by ID",
    description=(
        "Modify one or more details of an "
        "existing movie by its unique ID. "
        "Only the provided fields will be updated."
    ),
    status_code=status.HTTP_200_OK,
)
async def update_movie(
    movie_id: int,
    movie_data: MovieUpdateSchema,
    current_user=Depends(moderator_required),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with ID '{movie_id}' not found.",
        )

    for field, value in movie_data.model_dump(exclude_unset=True).items():
        setattr(movie, field, value)

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or duplicate data. Please verify your input.",
        )

    return {"detail": "Movie updated successfully."}


@router.delete(
    "/{movie_id}",
    summary="Delete movie by ID",
    description=(
        "Remove an existing movie from the database by its unique ID. "
        "If the movie does not exist, a 404 error will be returned."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_movie(
    movie_id: int,
    current_user=Depends(moderator_required),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with ID '{movie_id}' not found.",
        )

    stmt_order = select(OrderItem).where(OrderItem.movie_id == movie_id)
    result = await db.execute(stmt_order)
    order = result.scalars().first()

    if order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a movie that has been purchased by at least one user.",
        )

    await db.delete(movie)
    await db.commit()

    return
