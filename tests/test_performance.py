"""Bounded query counts and measured page latency; no hardware-dependent time gate."""
import json
import time
from statistics import median

from sqlalchemy import event, text
from app.services.admin_crud import AdminCrudService


async def test_lists_with_100_1000_10000_employees(db_factory, tmp_path):
    measurements = []
    query_count = 0
    engine = db_factory.kw['bind']
    def count(*args):
        nonlocal query_count
        query_count += 1
    event.listen(engine.sync_engine, 'before_cursor_execute', count)
    async with db_factory() as s:
        studio = await AdminCrudService(s).create_studio('Load fixture')
        previous = 0
        for size in (100, 1000, 10000):
            await s.execute(text("INSERT INTO users (telegram_id,full_name,studio_id) SELECT n, 'Employee ' || lpad(n::text, 6, '0'), :sid FROM generate_series(CAST(:start AS integer), CAST(:stop AS integer)) n"), {'sid':studio.id, 'start':previous+1, 'stop':size})
            await s.commit()
            values = []
            for _ in range(20):
                query_count = 0
                start = time.perf_counter()
                page = await AdminCrudService(s).users(limit=10, offset=size-10)
                values.append((time.perf_counter()-start)*1000)
                assert len(page) == 10
                assert query_count <= 2  # one page + one eager studio query, independent of population
            ordered = sorted(values)
            measurements.append({'users':size, 'median_ms':round(median(values),2), 'p95_ms':round(ordered[18],2), 'p99_ms':round(ordered[19],2), 'queries_per_page':query_count})
            previous = size
    event.remove(engine.sync_engine, 'before_cursor_execute', count)
    print('\nPERFORMANCE ' + json.dumps(measurements))
