from datetime import timedelta, datetime

class HOSState:
    OFF_DUTY = "off_duty"
    SLEEPER = "sleeper_berth"
    DRIVING = "driving"
    ON_DUTY = "on_duty"

class HOSSimulator:
    def __init__(self, start_time, initial_cycle_used=0.0):
        self.current_time = start_time
        self.logs = []
        self.timeline = []
        
        # State counters (hours)
        self.daily_driving = 0.0      # Max 11h
        self.daily_duty = 0.0         # Max 14h window (total duty time)
        self.driving_since_break = 0.0 # Max 8h (triggers 30m break)
        self.cycle_duty = initial_cycle_used # Max 70h in 8 days
        
        self.duty_window_start = None  # The timestamp when the 14h clock started
        self.total_distance = 0.0
        self.last_fuel_mile = 0.0
        
        self.violations = []

        # If starting cycle is already at limit, force restart immediately
        if self.cycle_duty >= 70.0:
            self.apply_rest(34.0, "Initial Cycle Limit Exceeded - Mandatory 34-Hour Restart Required")

    def add_event(self, status, duration_hrs, description, location=None, coords=None, reason=None):
        if duration_hrs <= 0:
            return

        start = self.current_time
        end = self.current_time + timedelta(hours=duration_hrs)
        
        # HOS Clock Management
        if status in [HOSState.DRIVING, HOSState.ON_DUTY]:
            if self.duty_window_start is None:
                self.duty_window_start = start
            
            self.cycle_duty += duration_hrs
            
            if status == HOSState.DRIVING:
                self.daily_driving += duration_hrs
                self.driving_since_break += duration_hrs
                
                # Check for violations (Double check logic)
                if self.daily_driving > 11.0001:
                    self.violations.append(f"11-Hour Limit Violated at {start.isoformat()}")
                if self.driving_since_break > 8.0001:
                    self.violations.append(f"8-Hour Break Rule Violated at {start.isoformat()}")

        # Add to logs and timeline
        self.logs.append({
            "status": status,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "duration": duration_hrs,
            "description": description
        })
        
        self.timeline.append({
            "time": start.isoformat(),
            "status": status,
            "description": description,
            "reason": reason,
            "location": location,
            "coords": coords,
            "distance_at_event": self.total_distance,
            "cycle_remaining": max(0, 70.0 - self.cycle_duty),
            "driving_since_rest": self.daily_driving,
            "window_remaining": 14.0 - ((start - self.duty_window_start).total_seconds() / 3600.0) if self.duty_window_start else 14.0
        })
        
        self.current_time = end

    def apply_rest(self, duration_hrs, reason):
        """Applies a rest period and resets relevant clocks."""
        self.add_event(HOSState.OFF_DUTY, duration_hrs, f"{duration_hrs}-Hour Mandatory Rest", reason=reason)
        
        # 30-min break resets the 8-hour driving clock
        if duration_hrs >= 0.5:
            self.driving_since_break = 0.0
            
        # 10-hour rest resets daily 11h driving and 14h window
        if duration_hrs >= 10.0:
            self.daily_driving = 0.0
            self.duty_window_start = None
            
        # 34-hour restart resets the 70h cycle
        if duration_hrs >= 34.0:
            self.cycle_duty = 0.0

    def simulate_driving(self, distance, duration, start_loc, end_loc):
        miles_left = distance
        hours_left = duration
        speed = distance / duration if duration > 0 else 60

        while miles_left > 0.01:
            # 1. Calculate the most restrictive limit
            # Time to 11h driving
            time_to_11h = max(0, 11.0 - self.daily_driving)
            
            # Time to 14h window expiry
            time_to_14h = 14.0
            if self.duty_window_start:
                elapsed_in_window = (self.current_time - self.duty_window_start).total_seconds() / 3600.0
                time_to_14h = max(0, 14.0 - elapsed_in_window)
            
            # Time to 8h driving break
            time_to_8h_break = max(0, 8.0 - self.driving_since_break)
            
            # Time to 70h cycle limit
            time_to_70h = max(0, 70.0 - self.cycle_duty)
            
            # Time to next fuel stop
            time_to_fuel = max(0, (1000.0 - (self.total_distance - self.last_fuel_mile)) / speed)
            
            # Take the smallest chunk possible before a rule is hit
            drive_chunk = min(time_to_11h, time_to_14h, time_to_8h_break, time_to_70h, time_to_fuel, hours_left)
            
            if drive_chunk > 0.001:
                self.add_event(HOSState.DRIVING, drive_chunk, f"Driving towards {end_loc}")
                self.total_distance += drive_chunk * speed
                miles_left -= drive_chunk * speed
                hours_left -= drive_chunk
            
            if miles_left <= 0.01:
                break

            # 2. Handle the specific clock that ran out
            if self.total_distance - self.last_fuel_mile >= 1000.0:
                self.add_event(HOSState.ON_DUTY, 0.5, "Fuel Stop", reason="1,000 mile fuel interval reached")
                self.last_fuel_mile = self.total_distance
                continue

            if self.cycle_duty >= 70.0:
                self.apply_rest(34.0, "70-Hour Cycle Exhausted - Mandatory 34-Hour Restart Required")
                continue

            if self.daily_driving >= 11.0:
                self.apply_rest(10.0, "11-Hour Driving Limit Reached - Mandatory 10-Hour Rest")
                continue

            if self.duty_window_start and (self.current_time - self.duty_window_start).total_seconds() / 3600.0 >= 14.0:
                self.apply_rest(10.0, "14-Hour Duty Window Expired - Mandatory 10-Hour Rest")
                continue

            if self.driving_since_break >= 8.0:
                self.apply_rest(0.5, "8-Hour Driving Limit Reached - Mandatory 30-Minute Break")
                continue

            # Safety break to avoid infinite loop if no progress made
            if drive_chunk <= 0.001:
                self.apply_rest(10.0, "System Forced Rest (Optimization Failure Protection)")
