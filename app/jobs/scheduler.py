from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from app.db.client import get_database
from app.jobs import sla_scanner

scheduler = AsyncIOScheduler()


async def start_scheduler():
    db = await get_database()
    
    scheduler.add_job(
        sla_scanner.scan_stat_slas,
        IntervalTrigger(minutes=5),
        args=[db],
        id="sla_scanner_stat",
        replace_existing=True
    )
    
    scheduler.add_job(
        sla_scanner.scan_urgent_slas,
        IntervalTrigger(minutes=10),
        args=[db],
        id="sla_scanner_urgent",
        replace_existing=True
    )
    
    scheduler.add_job(
        sla_scanner.scan_routine_slas,
        IntervalTrigger(minutes=30),
        args=[db],
        id="sla_scanner_routine",
        replace_existing=True
    )
    
    scheduler.add_job(
        sla_scanner.scan_nicu_slas,
        IntervalTrigger(minutes=5),
        args=[db],
        id="sla_scanner_nicu",
        replace_existing=True
    )

    scheduler.add_job(
        sla_scanner.scan_discharge_slas,
        IntervalTrigger(minutes=15),
        args=[db],
        id="sla_scanner_discharge",
        replace_existing=True
    )

    scheduler.add_job(
        sla_scanner.scan_chemo_slas,
        IntervalTrigger(minutes=30),
        args=[db],
        id="sla_scanner_chemo",
        replace_existing=True
    )

    scheduler.add_job(
        sla_scanner.run_flag_escalation,
        IntervalTrigger(minutes=60),
        args=[db],
        id="flag_escalation",
        replace_existing=True
    )
    
    scheduler.add_job(
        sla_scanner.generate_daily_report,
        CronTrigger(hour=0, minute=5),
        args=[db],
        id="daily_report",
        replace_existing=True
    )
    
    scheduler.start()


async def stop_scheduler():
    scheduler.shutdown()
