"""Initial schema for Bentonville Gas Simulator

Revision ID: 001
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create nodes table
    op.create_table(
        'nodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('node_type', sa.String(length=20), nullable=False),
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
        sa.Column('base_demand', sa.Float(), nullable=True, default=0.0),
        sa.Column('elevation', sa.Float(), nullable=True, default=0.0),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_nodes_id'), 'nodes', ['id'], unique=False)

    # Create pipes table
    op.create_table(
        'pipes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('length', sa.Float(), nullable=False),
        sa.Column('diameter', sa.Float(), nullable=False),
        sa.Column('roughness', sa.Float(), nullable=True, default=0.0001),
        sa.Column('material', sa.String(length=50), nullable=True, default='steel'),
        sa.Column('year_installed', sa.Integer(), nullable=True, default=2000),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['nodes.id'], ),
        sa.ForeignKeyConstraint(['target_id'], ['nodes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pipes_id'), 'pipes', ['id'], unique=False)

    # Create leaks table
    op.create_table(
        'leaks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.Column('severity', sa.Float(), nullable=True, default=1.0),
        sa.Column('detected', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('cleared_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_leaks_id'), 'leaks', ['id'], unique=False)

    # Create simulation_snapshots table
    op.create_table(
        'simulation_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_pressure', sa.Float(), nullable=False),
        sa.Column('demand_multiplier', sa.Float(), nullable=True, default=1.0),
        sa.Column('node_pressures', sa.JSON(), nullable=True),
        sa.Column('pipe_flow_rates', sa.JSON(), nullable=True),
        sa.Column('node_actual_demand', sa.JSON(), nullable=True),
        sa.Column('pipe_velocities', sa.JSON(), nullable=True),
        sa.Column('pipe_pressure_drops', sa.JSON(), nullable=True),
        sa.Column('pipe_reynolds', sa.JSON(), nullable=True),
        sa.Column('active_leaks', sa.JSON(), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=True, default=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_simulation_snapshots_id'), 'simulation_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_simulation_snapshots_is_current'), 'simulation_snapshots', ['is_current'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_simulation_snapshots_is_current'), table_name='simulation_snapshots')
    op.drop_index(op.f('ix_simulation_snapshots_id'), table_name='simulation_snapshots')
    op.drop_table('simulation_snapshots')
    
    op.drop_index(op.f('ix_leaks_id'), table_name='leaks')
    op.drop_table('leaks')
    
    op.drop_index(op.f('ix_pipes_id'), table_name='pipes')
    op.drop_table('pipes')
    
    op.drop_index(op.f('ix_nodes_id'), table_name='nodes')
    op.drop_table('nodes')
