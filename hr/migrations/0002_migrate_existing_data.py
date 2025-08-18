# Generated migration to handle existing production HR data

from django.db import migrations, models
from django.db.migrations.operations.base import Operation


class MigrateExistingHRDataOperation(Operation):
    """
    Custom operation to migrate existing HR data in production to match new schema.
    This handles the case where production has legacy HR tables that need to be
    updated to match the current Django models.
    """
    
    reversible = False
    
    def state_forwards(self, app_label, state):
        """No state changes needed - tables are already defined in initial migration"""
        pass
    
    def state_backwards(self, app_label, state):
        """This operation is not reversible"""
        pass
    
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        """Migrate existing data to match current schema"""
        with schema_editor.connection.cursor() as cursor:
            # Check if we're dealing with existing legacy tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = current_schema() 
                AND table_name LIKE 'hr_%'
            """)
            existing_tables = {row[0] for row in cursor.fetchall()}
            
            if not existing_tables:
                # No existing tables, this is a fresh installation
                print("Fresh installation - creating default work schedule")
                cursor.execute("""
                    INSERT INTO hr_workschedule (name, description, schedule_type)
                    VALUES ('Standard 9-5', 'Standard Monday to Friday, 9 AM to 5 PM', 'standard')
                    ON CONFLICT (name) DO NOTHING;
                """)
                return
            
            print(f"Found existing HR tables: {existing_tables}")
            
            # Handle hr_leavetype table updates
            if 'hr_leavetype' in existing_tables:
                print("Migrating hr_leavetype table...")
                
                # Add missing category column if it doesn't exist
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_schema = current_schema() 
                    AND table_name = 'hr_leavetype' AND column_name = 'category'
                """)
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE hr_leavetype ADD COLUMN category VARCHAR(20) DEFAULT 'paid'")
                    # Set categories based on name patterns
                    cursor.execute("UPDATE hr_leavetype SET category = 'sick' WHERE LOWER(name) LIKE '%sick%'")
                    cursor.execute("UPDATE hr_leavetype SET category = 'maternity' WHERE LOWER(name) LIKE '%maternity%' OR LOWER(name) LIKE '%paternity%'")
                    cursor.execute("UPDATE hr_leavetype SET category = 'emergency' WHERE LOWER(name) LIKE '%emergency%'")
                    cursor.execute("UPDATE hr_leavetype SET category = 'unpaid' WHERE LOWER(name) LIKE '%unpaid%'")
                    cursor.execute("UPDATE hr_leavetype SET category = 'annual' WHERE name LIKE '%Annual%'")
                    cursor.execute("ALTER TABLE hr_leavetype ALTER COLUMN category SET NOT NULL")
                
                # Rename columns to match model expectations
                column_renames = [
                    ('can_be_carried_over', 'allow_carry_over'),
                    ('notice_period_days', 'min_notice_days')
                ]
                
                for old_name, new_name in column_renames:
                    cursor.execute("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_schema = current_schema() 
                        AND table_name = 'hr_leavetype' AND column_name = %s
                    """, [old_name])
                    if cursor.fetchone():
                        cursor.execute(f"ALTER TABLE hr_leavetype RENAME COLUMN {old_name} TO {new_name}")
                
                # Add missing columns
                missing_columns = [
                    ('max_carry_over_days', 'DECIMAL(5,1) DEFAULT 0'),
                    ('max_consecutive_days', 'INTEGER'),
                    ('requires_medical_certificate', 'BOOLEAN DEFAULT false'),
                    ('medical_certificate_threshold_days', 'INTEGER'),
                    ('minimum_service_months', 'INTEGER DEFAULT 0'),
                    ('available_to_probationary', 'BOOLEAN DEFAULT true'),
                    ('gender_specific', 'VARCHAR(10) DEFAULT \'all\''),
                    ('is_paid', 'BOOLEAN DEFAULT true'),
                    ('color_code', 'VARCHAR(7) DEFAULT \'#3B82F6\'')
                ]
                
                for col_name, col_def in missing_columns:
                    cursor.execute("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_schema = current_schema() 
                        AND table_name = 'hr_leavetype' AND column_name = %s
                    """, [col_name])
                    if not cursor.fetchone():
                        cursor.execute(f"ALTER TABLE hr_leavetype ADD COLUMN {col_name} {col_def}")
            
            # Handle hr_leaverequest table updates
            if 'hr_leaverequest' in existing_tables:
                print("Migrating hr_leaverequest table...")
                
                # Check if leave_type is varchar (legacy) vs leave_type_id (new)
                cursor.execute("""
                    SELECT column_name, data_type FROM information_schema.columns 
                    WHERE table_schema = current_schema() 
                    AND table_name = 'hr_leaverequest' AND column_name = 'leave_type'
                """)
                leave_type_col = cursor.fetchone()
                
                if leave_type_col and leave_type_col[1] == 'character varying':
                    # Convert varchar leave_type to leave_type_id foreign key
                    cursor.execute("ALTER TABLE hr_leaverequest ADD COLUMN leave_type_id BIGINT")
                    # Set to first available leave type
                    cursor.execute("SELECT id FROM hr_leavetype LIMIT 1")
                    first_leave_type = cursor.fetchone()
                    if first_leave_type:
                        cursor.execute("UPDATE hr_leaverequest SET leave_type_id = %s", [first_leave_type[0]])
                    cursor.execute("ALTER TABLE hr_leaverequest ALTER COLUMN leave_type_id SET NOT NULL")
                    cursor.execute("ALTER TABLE hr_leaverequest ADD CONSTRAINT hr_leaverequest_leave_type_id_fkey FOREIGN KEY (leave_type_id) REFERENCES hr_leavetype(id)")
                    cursor.execute("ALTER TABLE hr_leaverequest DROP COLUMN leave_type")
                
                # Add missing columns
                missing_columns = [
                    ('duration_type', 'VARCHAR(20) DEFAULT \'full_day\''),
                    ('start_time', 'TIME'),
                    ('end_time', 'TIME'),
                    ('working_days_count', 'DECIMAL(5,1) DEFAULT 0'),
                    ('emergency_contact', 'VARCHAR(100)'),
                    ('handover_notes', 'TEXT'),
                    ('approval_date', 'TIMESTAMP WITH TIME ZONE'),
                    ('approval_comments', 'TEXT'),
                    ('medical_certificate', 'VARCHAR(100)'),
                    ('supporting_documents', 'VARCHAR(100)'),
                    ('submitted_at', 'TIMESTAMP WITH TIME ZONE'),
                    ('return_date', 'DATE'),
                    ('actual_return_date', 'DATE'),
                    ('hr_comments', 'TEXT')
                ]
                
                for col_name, col_def in missing_columns:
                    cursor.execute("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_schema = current_schema() 
                        AND table_name = 'hr_leaverequest' AND column_name = %s
                    """, [col_name])
                    if not cursor.fetchone():
                        cursor.execute(f"ALTER TABLE hr_leaverequest ADD COLUMN {col_name} {col_def}")
                
                # Convert total_days to decimal if it's integer
                cursor.execute("""
                    SELECT data_type FROM information_schema.columns 
                    WHERE table_schema = current_schema() 
                    AND table_name = 'hr_leaverequest' AND column_name = 'total_days'
                """)
                total_days_type = cursor.fetchone()
                if total_days_type and total_days_type[0] == 'integer':
                    cursor.execute("ALTER TABLE hr_leaverequest ALTER COLUMN total_days TYPE DECIMAL(5,1)")
            
            # Handle hr_leaverequestcomment table updates
            if 'hr_leaverequestcomment' in existing_tables:
                print("Migrating hr_leaverequestcomment table...")
                
                # Add missing author_id column
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_schema = current_schema() 
                    AND table_name = 'hr_leaverequestcomment' AND column_name = 'author_id'
                """)
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE hr_leaverequestcomment ADD COLUMN author_id BIGINT")
                    # Set default author from users table
                    cursor.execute("SELECT id FROM users_user LIMIT 1")
                    first_user = cursor.fetchone()
                    if first_user:
                        cursor.execute("UPDATE hr_leaverequestcomment SET author_id = %s WHERE author_id IS NULL", [first_user[0]])
                    cursor.execute("ALTER TABLE hr_leaverequestcomment ALTER COLUMN author_id SET NOT NULL")
                    cursor.execute("ALTER TABLE hr_leaverequestcomment ADD CONSTRAINT hr_leaverequestcomment_author_id_fkey FOREIGN KEY (author_id) REFERENCES users_user(id)")
                
                # Add missing is_internal column
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_schema = current_schema() 
                    AND table_name = 'hr_leaverequestcomment' AND column_name = 'is_internal'
                """)
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE hr_leaverequestcomment ADD COLUMN is_internal BOOLEAN DEFAULT false")
            
            # Create missing tables if they don't exist
            required_tables = {
                'hr_workschedule', 'hr_employeeleavebalance', 
                'hr_employeeworkschedule', 'hr_holiday'
            }
            missing_tables = required_tables - existing_tables
            
            for table in missing_tables:
                print(f"Creating missing table: {table}")
                if table == 'hr_workschedule':
                    cursor.execute("""
                        CREATE TABLE hr_workschedule (
                            id BIGSERIAL PRIMARY KEY,
                            name VARCHAR(100) UNIQUE NOT NULL,
                            description TEXT,
                            schedule_type VARCHAR(20) DEFAULT 'standard',
                            hours_per_day DECIMAL(4,2) DEFAULT 8.0,
                            hours_per_week DECIMAL(4,2) DEFAULT 40.0,
                            monday BOOLEAN DEFAULT true,
                            tuesday BOOLEAN DEFAULT true,
                            wednesday BOOLEAN DEFAULT true,
                            thursday BOOLEAN DEFAULT true,
                            friday BOOLEAN DEFAULT true,
                            saturday BOOLEAN DEFAULT false,
                            sunday BOOLEAN DEFAULT false,
                            start_time TIME DEFAULT '09:00:00',
                            end_time TIME DEFAULT '18:00:00',
                            break_duration_minutes INTEGER DEFAULT 60,
                            is_active BOOLEAN DEFAULT true,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                    """)
                    # Create default schedule
                    cursor.execute("""
                        INSERT INTO hr_workschedule (name, description, schedule_type)
                        VALUES ('Standard 9-5', 'Standard Monday to Friday, 9 AM to 5 PM', 'standard')
                        ON CONFLICT (name) DO NOTHING;
                    """)
                
                elif table == 'hr_employeeleavebalance':
                    cursor.execute("""
                        CREATE TABLE hr_employeeleavebalance (
                            id BIGSERIAL PRIMARY KEY,
                            employee_id BIGINT NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
                            leave_type_id BIGINT NOT NULL REFERENCES hr_leavetype(id) ON DELETE CASCADE,
                            year INTEGER NOT NULL,
                            allocated_days DECIMAL(5,1) DEFAULT 0.0,
                            used_days DECIMAL(5,1) DEFAULT 0.0,
                            pending_days DECIMAL(5,1) DEFAULT 0.0,
                            carried_over_days DECIMAL(5,1) DEFAULT 0.0,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            UNIQUE(employee_id, leave_type_id, year)
                        );
                    """)
                
                elif table == 'hr_employeeworkschedule':
                    cursor.execute("""
                        CREATE TABLE hr_employeeworkschedule (
                            id BIGSERIAL PRIMARY KEY,
                            employee_id BIGINT NOT NULL REFERENCES users_user(id) ON DELETE CASCADE,
                            work_schedule_id BIGINT NOT NULL REFERENCES hr_workschedule(id) ON DELETE CASCADE,
                            effective_from DATE NOT NULL,
                            effective_to DATE,
                            is_active BOOLEAN DEFAULT true,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                    """)
                
                elif table == 'hr_holiday':
                    cursor.execute("""
                        CREATE TABLE hr_holiday (
                            id BIGSERIAL PRIMARY KEY,
                            name VARCHAR(100) NOT NULL,
                            date DATE NOT NULL,
                            is_recurring BOOLEAN DEFAULT false,
                            description TEXT,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            UNIQUE(name, date)
                        );
                    """)
            
            print("Migration completed successfully!")
    
    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        """This operation is not reversible"""
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0001_initial'),
    ]

    operations = [
        MigrateExistingHRDataOperation(),
    ]
