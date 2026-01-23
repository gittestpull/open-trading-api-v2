                // Helper to format scheduler jobs info
                let scheduleInfo = '<span class="text-gray-500">Not Scheduled</span>';
                if (scheduler.is_running && scheduler.jobs && scheduler.jobs.length > 0) {
                    // Extract next run time from the first job (usually we only have 'daily_collection')
                    const job = scheduler.jobs[0];
                    if (job.next_run) {
                        const nextDate = new Date(job.next_run);
                        // Format: HH:mm (KST)
                        const timeStr = nextDate.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
                        scheduleInfo = `<span class="text-accent-yellow">${timeStr}</span>`;
                    }
                }

                document.getElementById('schedulerStatus').innerHTML = `
                    <div class="flex justify-between"><span class="text-gray-500">Status</span><span class="${scheduler.is_running ? 'text-accent-green' : 'text-gray-500'}">${scheduler.is_running ? 'Running' : 'Stopped'}</span></div>
                    <div class="flex justify-between"><span class="text-gray-500">Mode</span><span>${scheduler.is_live ? 'LIVE' : 'Demo'}</span></div>
                    <div class="flex justify-between"><span class="text-gray-500">Scheduled Time</span>${scheduleInfo}</div>
                    <div class="flex justify-between"><span class="text-gray-500">Last Collection</span><span>${scheduler.last_collection ? scheduler.last_collection.substring(11, 16) : 'Never'}</span></div>
                `;
