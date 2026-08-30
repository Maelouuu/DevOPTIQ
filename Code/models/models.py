# Code/models/models.py
from datetime import datetime
from flask import session
from sqlalchemy import or_
from Code.extensions import db

# -------------------------------------------------------------------
# Tables d'association (déclarées UNE seule fois + extend_existing)
# -------------------------------------------------------------------
task_tools = db.Table(
    'task_tools',
    db.Column('task_id', db.Integer, db.ForeignKey('tasks.id'), primary_key=True),
    db.Column('tool_id', db.Integer, db.ForeignKey('tools.id'), primary_key=True),
    extend_existing=True
)

activity_roles = db.Table(
    'activity_roles',
    db.Column('activity_id', db.Integer, db.ForeignKey('activities.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('status', db.String(50), nullable=False),
    # V1.1 — CDC 3.4 : niveau de maîtrise REQUIS par le couple Rôle × Activité (0..4 ou NULL).
    # Défaut 2 pour l'association Garant ; NULL pour les autres tant qu'il n'est pas défini.
    db.Column('required_mastery_level', db.Integer, nullable=True),
    extend_existing=True
)

task_roles = db.Table(
    'task_roles',
    db.Column('task_id', db.Integer, db.ForeignKey('tasks.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('status', db.String(50), nullable=False),
    extend_existing=True
)


# -------------------------------------------------------------------
# Modèle Entity (Organisation/Entreprise)
# -------------------------------------------------------------------
class Entity(db.Model):
    """
    Représente une organisation/entreprise avec sa cartographie.
    Chaque entité possède ses propres données (activités, rôles, etc.)
    et appartient à un utilisateur (owner_id).
    
    L'entité ACTIVE est stockée dans la session utilisateur (pas en base).
    """
    __tablename__ = 'entities'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Propriétaire de l'entité (user qui l'a créée)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    
    # Fichier SVG actif pour cette entité
    svg_filename = db.Column(db.String(255), nullable=True)
    # Contenu SVG stocké en base (survit aux redémarrages serveur cloud)
    svg_content = db.Column(db.Text, nullable=True)
    # Nom original du fichier VSDX uploadé (pour affichage dans popup)
    vsdx_filename = db.Column(db.String(255), nullable=True)
    # Cartographie OptiqCarto sérialisée en JSON (survit aux redémarrages cloud)
    optiqcarto_data = db.Column(db.Text, nullable=True)

    # DEPRECATED: is_active n'est plus utilisé, l'entité active est dans la session
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    activities = db.relationship('Activities', backref='entity', lazy=True, cascade="all, delete-orphan")
    data = db.relationship('Data', backref='entity', lazy=True, cascade="all, delete-orphan")
    roles = db.relationship('Role', backref='entity', lazy=True, cascade="all, delete-orphan")
    tools = db.relationship('Tool', backref='entity', lazy=True, cascade="all, delete-orphan")
    links = db.relationship('Link', backref='entity', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Entity {self.id}: {self.name}>'
    
    @classmethod
    def get_active(cls, user_id=None):
        """
        Retourne l'entité active pour l'utilisateur courant.
        L'ID de l'entité active est stocké dans session['active_entity_id'].
        STRICT: Ne retourne que les entités appartenant à l'utilisateur.
        """
        if user_id is None:
            user_id = session.get('user_id')
        
        if not user_id:
            return None  # Pas connecté = pas d'entité
        
        active_entity_id = session.get('active_entity_id')
        
        if active_entity_id:
            # Vérifier que l'entité appartient à cet utilisateur
            entity = cls.query.filter(
                cls.id == active_entity_id,
                cls.owner_id == user_id
            ).first()
            
            if entity:
                return entity
        
        # Fallback: retourner la première entité de l'utilisateur
        first_entity = cls.query.filter_by(owner_id=user_id).first()
        
        if first_entity:
            session['active_entity_id'] = first_entity.id
            return first_entity
        
        return None
    
    @classmethod
    def get_active_id(cls, user_id=None):
        """Retourne l'ID de l'entité active (ou None)."""
        entity = cls.get_active(user_id)
        return entity.id if entity else None
    
    @classmethod
    def set_active(cls, entity_id, user_id=None):
        """
        Définit une entité comme active pour l'utilisateur courant.
        Stocke l'ID dans la session (pas en base).
        STRICT: Ne permet d'activer que les entités appartenant à l'utilisateur.
        """
        if user_id is None:
            user_id = session.get('user_id')
        
        if not user_id:
            return None  # Pas connecté
        
        # Vérifier que l'entité appartient à cet utilisateur
        entity = cls.query.filter_by(id=entity_id, owner_id=user_id).first()
        
        if entity:
            session['active_entity_id'] = entity.id
            return entity
        
        return None
    
    @classmethod
    def for_user(cls, user_id=None):
        """
        Retourne les entités appartenant à un utilisateur.
        STRICT: Ne retourne que les entités avec owner_id correspondant.
        """
        if user_id is None:
            user_id = session.get('user_id')
        
        if user_id:
            return cls.query.filter_by(owner_id=user_id).order_by(cls.name)
        
        # Pas connecté = pas d'entités
        return cls.query.filter(cls.id < 0)  # Query vide
        return cls.query.order_by(cls.name)


# -------------------------------------------------------------------
# Modèles principaux
# -------------------------------------------------------------------
class Activities(db.Model):
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=True, index=True)
    shape_id = db.Column(db.String(50), index=True, nullable=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_result = db.Column(db.Boolean, nullable=False, default=False)
    shape_subtype = db.Column(db.String(50), nullable=True)  # 'normal', 'external', 'extco', 'special'
    # V1.1 — CDC 5 : cadence de l'activité (code interne EVENT/DAILY/WEEKLY… + précisions).
    cadence_code = db.Column(db.String(20), nullable=True)
    cadence_details = db.Column(db.Text, nullable=True)

    # Durée/délai (défaut / préremplissage des autres pages)
    duration_minutes = db.Column(db.Float, default=0)
    delay_minutes = db.Column(db.Float, default=0)

    tasks = db.relationship(
        'Task',
        backref='activity',
        lazy=True,
        order_by='Task.order',
        cascade="all, delete-orphan"
    )
    competencies = db.relationship('Competency', backref='activity', lazy=True, cascade="all, delete-orphan")
    softskills = db.relationship('Softskill', backref='activity', lazy=True, cascade="all, delete-orphan")
    constraints = db.relationship('Constraint', backref='activity', lazy=True, cascade="all, delete-orphan")
    savoirs = db.relationship('Savoir', backref='activity', lazy=True, cascade="all, delete-orphan")
    savoir_faires = db.relationship('SavoirFaire', backref='activity', lazy=True, cascade="all, delete-orphan")
    aptitudes = db.relationship('Aptitude', backref='activity', lazy=True, cascade="all, delete-orphan")

    # Contrainte unique: shape_id unique par entité
    __table_args__ = (
        db.UniqueConstraint('entity_id', 'shape_id', name='uq_entity_shape'),
    )

    # =============================================
    # HELPER : Filtrer par entité active
    # =============================================
    @classmethod
    def for_active_entity(cls):
        """
        Retourne une query filtrée par l'entité active.
        Usage: Activities.for_active_entity().all()
        """
        active_entity_id = Entity.get_active_id()
        if active_entity_id:
            return cls.query.filter_by(entity_id=active_entity_id)
        # Si pas d'entité active, retourner query vide
        return cls.query.filter(cls.id < 0)


class Data(db.Model):
    __tablename__ = 'data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=True, index=True)
    shape_id = db.Column(db.String(50), index=True, nullable=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    layer = db.Column(db.String(50), nullable=True)

    # V1.1 — CDC 1 : nature sémantique de la donnée de sortie (≠ Data.type qui est le type de flux).
    # Codes techniques internes, jamais affichés tels quels : RESULT | MEASURE | EVENT | INFORMATION.
    # NULL = donnée pas encore qualifiée.
    semantic_nature = db.Column(db.String(20), nullable=True)
    # Standard minimal de performance — surtout pour RESULT : « à partir de quel niveau l'activité
    # est-elle considérée tenue de manière autonome (niveau 2) ? ». Proposé IA, corrigé utilisateur.
    minimum_performance_text = db.Column(db.Text, nullable=True)
    qualification_source = db.Column(db.String(10), nullable=True)      # AI | MANUAL
    qualification_updated_at = db.Column(db.DateTime, nullable=True)
    # V1.1 — CDC 5.4 : cadence et fraîcheur de la donnée.
    update_cadence_code = db.Column(db.String(20), nullable=True)
    max_age_hours = db.Column(db.Integer, nullable=True)
    # V1.1 — CDC 1/§8 : une « donnée de sortie » d'une activité EST une connexion sortante
    # (Link) de la carto. Les Link sont supprimés/recréés à chaque sauvegarde de carto, donc la
    # qualification métier (nature, standard) ne peut PAS vivre sur le Link. On matérialise chaque
    # sortie en une ligne Data durable, ancrée à son activité productrice via ce champ. Ces Data
    # n'ont pas de shape_id → invisibles dans la carto, jamais touchées par la re-synchro.
    producer_activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=True, index=True)

    __table_args__ = (
        db.UniqueConstraint('entity_id', 'shape_id', name='uq_entity_data_shape'),
    )

    @classmethod
    def for_active_entity(cls):
        active_entity_id = Entity.get_active_id()
        if active_entity_id:
            return cls.query.filter_by(entity_id=active_entity_id)
        return cls.query.filter(cls.id < 0)


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    order = db.Column(db.Integer, nullable=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)

    # Durée/délai par tâche
    duration_minutes = db.Column(db.Float, default=0)
    delay_minutes = db.Column(db.Float, default=0)

    # Pièce jointe de la tâche — distincte de celle d'un outil : le mode
    # opératoire de la tâche n'est pas la notice de l'outil qu'elle utilise.
    file_path = db.Column(db.String(512), nullable=True)

    tools = db.relationship(
        'Tool',
        secondary=task_tools,
        lazy='subquery',
        backref=db.backref('tasks', lazy=True)
    )


class Tool(db.Model):
    __tablename__ = 'tools'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(512), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('entity_id', 'name', name='uq_entity_tool_name'),
    )

    @classmethod
    def for_active_entity(cls):
        active_entity_id = Entity.get_active_id()
        if active_entity_id:
            return cls.query.filter_by(entity_id=active_entity_id)
        return cls.query.filter(cls.id < 0)


class Competency(db.Model):
    __tablename__ = 'competencies'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    description = db.Column(db.Text, nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)


class Softskill(db.Model):
    __tablename__ = 'softskills'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    habilete = db.Column(db.String(255), nullable=False)
    niveau = db.Column(db.String(10), nullable=False)
    justification = db.Column(db.Text, nullable=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    # Caches de traduction du nom (affichage selon la langue de l'interface).
    # `name` reste la saisie d'origine ; name_fr/name_en sont remplis à la
    # création/renommage (langue courante) puis à la volée par IA pour l'autre.
    name_fr = db.Column(db.String(200), nullable=True)
    name_en = db.Column(db.String(200), nullable=True)
    onboarding_plan = db.Column(db.Text, nullable=True)
    mission_generale = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('entity_id', 'name', name='uq_entity_role_name'),
    )

    @classmethod
    def for_active_entity(cls):
        active_entity_id = Entity.get_active_id()
        if active_entity_id:
            return cls.query.filter_by(entity_id=active_entity_id)
        return cls.query.filter(cls.id < 0)


class Link(db.Model):
    __tablename__ = 'links'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=True, index=True)
    source_activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=True)
    source_data_id = db.Column(db.Integer, db.ForeignKey('data.id'), nullable=True)
    target_activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=True)
    target_data_id = db.Column(db.Integer, db.ForeignKey('data.id'), nullable=True)
    type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    cross_carto_liaison_id = db.Column(db.Integer, nullable=True)
    cross_carto_label = db.Column(db.String(200), nullable=True)
    choice_label = db.Column(db.String(10), nullable=True)  # 'Oui'/'Non' when source is a decision diamond

    @property
    def source_id(self):
        return self.source_activity_id if self.source_activity_id is not None else self.source_data_id

    @property
    def target_id(self):
        return self.target_activity_id if self.target_activity_id is not None else self.target_data_id

    @classmethod
    def for_active_entity(cls):
        active_entity_id = Entity.get_active_id()
        if active_entity_id:
            return cls.query.filter_by(entity_id=active_entity_id)
        return cls.query.filter(cls.id < 0)


class Performance(db.Model):
    __tablename__ = 'performances'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    link_id = db.Column(db.Integer, db.ForeignKey('links.id', ondelete='CASCADE'), unique=True)
    link = db.relationship('Link', backref=db.backref('performance', uselist=False))


class PerformancePersonnalisee(db.Model):
    __tablename__ = 'performance_personnalisee'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)
    activity_id = db.Column(db.Integer, nullable=False)

    content = db.Column('content', db.Text, nullable=True)
    validation_status = db.Column(db.String(20), default='non-validee')
    validation_date = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.Text, default=lambda: datetime.utcnow().isoformat())
    updated_at = db.Column(db.Text, default=lambda: datetime.utcnow().isoformat())
    deleted = db.Column(db.Boolean, default=False)


class Constraint(db.Model):
    __tablename__ = 'constraints'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    description = db.Column(db.Text, nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    file_path = db.Column(db.String(512), nullable=True)


class Savoir(db.Model):
    __tablename__ = 'savoirs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    description = db.Column(db.Text, nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)


class SavoirFaire(db.Model):
    __tablename__ = 'savoir_faires'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    description = db.Column(db.Text, nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)


class Aptitude(db.Model):
    __tablename__ = 'aptitudes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    description = db.Column(db.Text, nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=True, index=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    email = db.Column(db.String(200), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='user')
    # Langue de l'interface, propre au compte. L'anglais est la langue par
    # défaut du produit ; seuls les comptes de DEFAULT_FRENCH_ACCOUNTS naissent
    # en français. Modifiable ensuite depuis Paramètres.
    lang = db.Column(db.String(5), nullable=False, default='en', server_default='en')
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    subordinates = db.relationship('User', backref=db.backref('manager', remote_side=[id]))
    evaluations = db.relationship('CompetencyEvaluation', back_populates='user',
                                  foreign_keys='CompetencyEvaluation.user_id', cascade='all, delete-orphan')

    @classmethod
    def for_active_entity(cls):
        active_entity_id = Entity.get_active_id()
        if active_entity_id:
            return cls.query.filter_by(entity_id=active_entity_id)
        return cls.query.filter(cls.id < 0)


# Langue servie quand rien n'est précisé (compte, session).
DEFAULT_LANG = 'en'

# Comptes qui restent en français malgré le défaut anglais.
DEFAULT_FRENCH_ACCOUNTS = {'afdec.enterprise.services@gmail.com'}


def default_lang_for(email):
    """Langue initiale d'un compte, d'après son e-mail."""
    return 'fr' if (email or '').strip().lower() in DEFAULT_FRENCH_ACCOUNTS else DEFAULT_LANG


class UserRole(db.Model):
    __tablename__ = 'user_roles'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), primary_key=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', backref='user_roles', foreign_keys=[user_id])
    role = db.relationship('Role', backref='user_roles')
    manager = db.relationship('User', foreign_keys=[manager_id])


class EntrepriseSettings(db.Model):
    """Paramètres de temps de travail de l'entreprise (par entité).

    Historiquement gérée en SQL brut sans modèle : la table n'était donc
    jamais créée par create_all() en production, et la section « Paramètres
    de l'entreprise » de la page Gestion RH restait vide.
    """
    __tablename__ = 'entreprise_settings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    work_hours_per_day = db.Column(db.Float, nullable=True)
    work_days_per_week = db.Column(db.Float, nullable=True)
    work_weeks_per_year = db.Column(db.Float, nullable=True)
    work_days_per_year = db.Column(db.Float, nullable=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)


class CompetencyEvaluation(db.Model):
    __tablename__ = 'competency_evaluation'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)

    item_id = db.Column(db.Integer, nullable=True)
    item_type = db.Column(db.String(50), nullable=True)
    eval_number = db.Column(db.String(50), nullable=False)
    note = db.Column(db.String(10), nullable=False)      # legacy couleur — conservé pour compat
    created_at = db.Column(db.Text, default=datetime.utcnow)

    # V1.1 — CDC 3.5 : évaluation par RÉSULTAT. Pour un RESULT : item_type='activity_results',
    # item_id=data_id. La couleur devient calculée depuis mastery_level + écart au requis.
    mastery_level = db.Column(db.Integer, nullable=True)          # 0..4
    evidence = db.Column(db.Text, nullable=True)
    evaluated_at = db.Column(db.DateTime, nullable=True)
    evaluator_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    user = db.relationship('User', back_populates='evaluations', foreign_keys=[user_id])

    __table_args__ = (
        db.UniqueConstraint('user_id', 'activity_id', 'item_id', 'item_type', 'eval_number'),
    )


class ResultCapabilityLink(db.Model):
    """V1.1 — CDC 2.7 : relie un RÉSULTAT (Data.semantic_nature = RESULT) aux savoirs,
    savoir-faire et HSC nécessaires pour le produire. Sert au DIAGNOSTIC d'un écart : quand
    un résultat n'est pas tenu, on n'affiche que les capacités reliées à CE résultat.
    Un même S/SF/HSC peut être relié à plusieurs résultats (une ligne par lien)."""
    __tablename__ = 'result_capability_links'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=True, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False, index=True)
    data_id = db.Column(db.Integer, db.ForeignKey('data.id'), nullable=False, index=True)  # → RESULT
    item_type = db.Column(db.String(20), nullable=False)   # SAVOIR | SAVOIR_FAIRE | HSC
    item_id = db.Column(db.Integer, nullable=False)
    required_level = db.Column(db.Integer, nullable=True)   # 1..4 (nullable à la migration)
    source = db.Column(db.String(10), nullable=True)        # AI | MANUAL
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('activity_id', 'data_id', 'item_type', 'item_id', name='uq_result_capability'),
    )


class ResultDiagnostic(db.Model):
    """V1.1 — CDC 6.6 : diagnostic d'un écart sur un RÉSULTAT pour un individu. Trois familles
    de causes possibles (WORK_ARCHITECTURE, ABILITY_TO_ACT, EXECUTION_CONDITIONS). L'IA propose,
    le Garant/Manager valide. Seule ABILITY_TO_ACT justifie un plan de développement individuel."""
    __tablename__ = 'result_diagnostics'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False, index=True)
    data_id = db.Column(db.Integer, db.ForeignKey('data.id'), nullable=False, index=True)  # RESULT
    families = db.Column(db.Text, nullable=True)         # JSON : liste de codes familles validés
    note = db.Column(db.Text, nullable=True)
    validated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'activity_id', 'data_id', name='uq_result_diagnostic'),
    )


class TechnicalDomain(db.Model):
    """V1.1 — CDC 4 : domaine de technicité (« Technical domain », jamais « expertise domain » —
    Expertise = niveau 4). Permet qu'une même activité soit exercée dans des contextes techniques
    différents (Plastic/Metal, Français/Maths…) sans dupliquer l'activité."""
    __tablename__ = 'technical_domains'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=True, index=True)
    name_fr = db.Column(db.String(150), nullable=False)
    name_en = db.Column(db.String(150), nullable=True)
    description = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True)


class ActivityTechnicalDomain(db.Model):
    __tablename__ = 'activity_technical_domains'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False, index=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('technical_domains.id'), nullable=False, index=True)
    __table_args__ = (db.UniqueConstraint('activity_id', 'domain_id', name='uq_activity_domain'),)


class RoleActivityDomainRequirement(db.Model):
    """Niveau technique REQUIS par le rôle sur une activité, pour un domaine donné."""
    __tablename__ = 'role_activity_domain_requirements'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False, index=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('technical_domains.id'), nullable=False, index=True)
    required_level = db.Column(db.Integer, nullable=True)   # 0..4
    __table_args__ = (db.UniqueConstraint('role_id', 'activity_id', 'domain_id', name='uq_role_activity_domain'),)


class UserDomainLevel(db.Model):
    """Niveau technique DÉMONTRÉ par l'individu sur un domaine (axe séparé du niveau d'activité)."""
    __tablename__ = 'user_domain_levels'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('technical_domains.id'), nullable=False, index=True)
    demonstrated_level = db.Column(db.Integer, nullable=True)   # 0..4
    evidence = db.Column(db.Text, nullable=True)
    evaluated_at = db.Column(db.DateTime, nullable=True)
    evaluator_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    __table_args__ = (db.UniqueConstraint('user_id', 'domain_id', name='uq_user_domain'),)


class HscLevelDescriptor(db.Model):
    """V1.1 — CDC 7.3 : référentiel comportemental des 16 HSC, 4 niveaux chacune. Sert à
    l'auto-positionnement (comportements observables) plutôt qu'un choix direct de niveau."""
    __tablename__ = 'hsc_level_descriptors'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=True, index=True)
    hsc_name = db.Column(db.String(150), nullable=False, index=True)
    level = db.Column(db.Integer, nullable=False)              # 1..4
    descriptor_fr = db.Column(db.Text, nullable=True)
    descriptor_en = db.Column(db.Text, nullable=True)
    observable_behaviors_fr = db.Column(db.Text, nullable=True)
    observable_behaviors_en = db.Column(db.Text, nullable=True)
    example_situations_fr = db.Column(db.Text, nullable=True)
    example_situations_en = db.Column(db.Text, nullable=True)
    development_focus_fr = db.Column(db.Text, nullable=True)
    development_focus_en = db.Column(db.Text, nullable=True)
    __table_args__ = (db.UniqueConstraint('entity_id', 'hsc_name', 'level', name='uq_hsc_level'),)


class TimeAnalysis(db.Model):
    __tablename__ = 'time_analysis'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    duration = db.Column(db.Integer, nullable=False)
    recurrence = db.Column(db.String(20), nullable=False)
    frequency = db.Column(db.Integer, nullable=False)
    delay = db.Column(db.Integer, nullable=True)

    type = db.Column(db.String(20), nullable=False)

    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    nb_people = db.Column(db.Integer, nullable=False, default=1)
    impact_unit = db.Column(db.String(20), nullable=True)
    delay_increase = db.Column(db.Float, nullable=True)
    delay_percentage = db.Column(db.Float, nullable=True)

    activity = db.relationship('Activities', backref='time_analyses')
    task = db.relationship('Task', backref='time_analyses')
    role = db.relationship('Role', backref='time_analyses')
    user = db.relationship('User', backref='time_analyses')

    @property
    def recurrence_factor(self):
        return {
            "journalier": 220,
            "hebdo": 42,
            "mensuel": 10.5,
            "annuel": 1
        }.get(self.recurrence, 0)

    @property
    def annual_time(self):
        return self.duration * self.recurrence_factor * self.frequency * self.nb_people

    @property
    def delay_gap(self):
        if self.delay and self.delay_increase:
            return self.delay + self.delay_increase
        elif self.delay:
            return self.delay
        else:
            return self.delay_increase or 0

    @property
    def delay_ratio(self):
        if self.delay and self.delay_increase:
            try:
                return round((self.delay_increase / self.delay) * 100, 1)
            except ZeroDivisionError:
                return 0
        return 0


# -------------------------------------------------------------------
# Modèles "Temps"
# -------------------------------------------------------------------
class TimeProject(db.Model):
    __tablename__ = 'time_project'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=True, index=True)
    name = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lines = db.relationship('TimeProjectLine', backref='project', cascade="all, delete-orphan")

    @classmethod
    def for_active_entity(cls):
        active_entity_id = Entity.get_active_id()
        if active_entity_id:
            return cls.query.filter_by(entity_id=active_entity_id)
        return cls.query.filter(cls.id < 0)


class TimeProjectLine(db.Model):
    __tablename__ = 'time_project_line'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, db.ForeignKey('time_project.id', ondelete="CASCADE"), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    duration_minutes = db.Column(db.Float, nullable=False, default=0)
    delay_minutes = db.Column(db.Float, nullable=False, default=0)
    nb_people = db.Column(db.Integer, nullable=False, default=1)


class TimeRoleAnalysis(db.Model):
    __tablename__ = 'time_role_analysis'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    name = db.Column(db.String(120), default='Analyse rôle')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lines = db.relationship('TimeRoleLine', backref='role_analysis', cascade="all, delete-orphan")


class TimeRoleLine(db.Model):
    __tablename__ = 'time_role_line'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_analysis_id = db.Column(db.Integer, db.ForeignKey('time_role_analysis.id', ondelete="CASCADE"), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    recurrence = db.Column(db.String(32), nullable=False)
    frequency = db.Column(db.Integer, nullable=False, default=1)
    duration_minutes = db.Column(db.Float, nullable=False, default=0)
    delay_minutes = db.Column(db.Float, nullable=False, default=0)
    nb_people = db.Column(db.Integer, nullable=False, default=1)


class TimeWeakness(db.Model):
    __tablename__ = 'time_weakness'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    duration_std_minutes = db.Column(db.Float, nullable=False, default=0)
    delay_std_minutes = db.Column(db.Float, nullable=False, default=0)
    recurrence = db.Column(db.String(32), nullable=False)
    frequency = db.Column(db.Integer, nullable=False, default=1)
    weakness = db.Column(db.Text)
    work_added_qty = db.Column(db.Float, nullable=False, default=0)
    work_added_unit = db.Column(db.String(16), nullable=False, default='minutes')
    wait_added_qty = db.Column(db.Float, nullable=False, default=0)
    wait_added_unit = db.Column(db.String(16), nullable=False, default='minutes')
    prob_denom = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CartoCalque(db.Model):
    """Calque d'une cartographie — déclinaison indépendante de la carto de base d'une entité."""
    __tablename__ = 'carto_calques'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_id  = db.Column(db.Integer, db.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False)
    name       = db.Column(db.String(200), nullable=False)
    state_json = db.Column(db.Text, nullable=False)   # état complet (bands/shapes/connections/…)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    entity = db.relationship('Entity', backref=db.backref('calques', cascade='all, delete-orphan', lazy='dynamic'))


class FileBlob(db.Model):
    """Stocke le contenu binaire des fichiers liés aux outils et contraintes.
    Persistant en base (PostgreSQL BYTEA / SQLite BLOB) — survit aux redémarrages cloud."""
    __tablename__ = 'file_blobs'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filename   = db.Column(db.String(255), nullable=False)
    mimetype   = db.Column(db.String(128), nullable=False, default='application/octet-stream')
    data       = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TaskLinkAssignment(db.Model):
    """Associe une connexion (link) à une tâche, avec une direction ('incoming' ou 'outgoing')."""
    __tablename__ = 'task_link_assignments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    link_id = db.Column(db.Integer, db.ForeignKey('links.id', ondelete='CASCADE'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    direction = db.Column(db.String(20), nullable=False)  # 'incoming' ou 'outgoing'

    __table_args__ = (
        db.UniqueConstraint('link_id', 'direction', name='uq_task_link_dir'),
    )


def _event_label(cle):
    """Libelle d'evenement dans la langue de la session (repli francais)."""
    from Code.translations import t
    return t(cle)


class RecentEvent(db.Model):
    """Journal d'activité récente : créations/modifications/suppressions des 4 entités principales."""
    __tablename__ = 'recent_events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_type = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(80), nullable=False, default='fa-solid fa-circle')
    label = db.Column(db.String(255), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    detail = db.Column(db.Text, nullable=True)   # JSON — avant/après ou données de création
    user_id = db.Column(db.Integer, nullable=True)  # utilisateur à l'origine de l'action


class EntityShareOffer(db.Model):
    """Proposition de partage d'entité en attente de réponse.

    Un administrateur dépose directement sa copie chez le destinataire ; tout
    autre compte ne peut que PROPOSER. Le contenu de la carto est recopié ici
    au moment de l'envoi : le destinataire reçoit ce qui lui a été proposé,
    même si l'expéditeur modifie ou supprime son entité entre-temps.
    """
    __tablename__ = 'entity_share_offers'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    from_user_id = db.Column(db.Integer, nullable=False, index=True)
    to_user_id = db.Column(db.Integer, nullable=False, index=True)
    source_entity_id = db.Column(db.Integer, nullable=True)

    entity_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    vsdx_filename = db.Column(db.String(255), nullable=True)
    svg_filename = db.Column(db.String(255), nullable=True)
    svg_content = db.Column(db.Text, nullable=True)
    optiqcarto_data = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), nullable=False, default='pending')
    # pending|accepted|declined (proposition) — delivered|acknowledged (dépôt d'autorité)
    deposit_kind = db.Column(db.String(20), nullable=True)  # copy|replace
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)
    created_entity_id = db.Column(db.Integer, nullable=True)


# -------------------------------------------------------------------
# SQLAlchemy event listeners — journal d'activité automatique
# -------------------------------------------------------------------
import json as _json
from sqlalchemy import event, inspect as _sa_inspect
from sqlalchemy import text as _sql_text


def _log_recent(connection, event_type, icon, label, entity_id=None, detail=None):
    """Insère un événement récent via la connexion active (dans la même transaction)."""
    try:
        # Récupérer l'utilisateur depuis la session Flask (disponible dans le contexte de requête)
        user_id = None
        try:
            from flask import session as _fs
            user_id = _fs.get('user_id')
        except Exception:
            pass

        detail_str = _json.dumps(detail, ensure_ascii=False) if detail else None
        connection.execute(
            _sql_text(
                "INSERT INTO recent_events "
                "(event_type, icon, label, entity_id, created_at, detail, user_id) "
                "VALUES (:et, :icon, :label, :eid, :ts, :detail, :uid)"
            ),
            {"et": event_type, "icon": icon, "label": label,
             "eid": entity_id, "ts": datetime.utcnow(),
             "detail": detail_str, "uid": user_id}
        )
    except Exception:
        pass  # Table absente ou colonne manquante — ignoré silencieusement


def _capture_changes(target, fields):
    """Retourne la liste des champs modifiés avec avant/après via l'historique SQLAlchemy."""
    try:
        state = _sa_inspect(target)
        changes = []
        for field, label in fields.items():
            hist = state.attrs[field].history
            if hist.deleted:
                before = str(hist.deleted[0] or "—")
                after  = str(hist.added[0] if hist.added else getattr(target, field, "—") or "—")
                if before != after:
                    changes.append({"field": label, "before": before, "after": after})
        return changes
    except Exception:
        return []


# ── Activities ────────────────────────────────────────────────────
@event.listens_for(Activities, 'after_insert')
def _on_activity_insert(mapper, connection, target):
    detail = {"name": target.name, "description": target.description or ""}
    _log_recent(connection, 'activity_created', 'fa-solid fa-diagram-project',
                f'{_event_label("event.activity_created")} : {target.name}', target.entity_id, detail=detail)


@event.listens_for(Activities, 'before_update')
def _before_activity_update(mapper, connection, target):
    target._prev_changes = _capture_changes(target, {"name": "Nom", "description": "Description"})


@event.listens_for(Activities, 'after_update')
def _on_activity_update(mapper, connection, target):
    changes = getattr(target, '_prev_changes', None) or []
    detail = {"changes": changes} if changes else None
    _log_recent(connection, 'activity_updated', 'fa-solid fa-pen-to-square',
                f'{_event_label("event.activity_updated")} : {target.name}', target.entity_id, detail=detail)


# ── Tasks ─────────────────────────────────────────────────────────
@event.listens_for(Task, 'after_insert')
def _on_task_insert(mapper, connection, target):
    detail = {"name": target.name, "description": target.description or ""}
    _log_recent(connection, 'task_created', 'fa-solid fa-list-check',
                f'{_event_label("event.task_created")} : {target.name}', detail=detail)


@event.listens_for(Task, 'before_update')
def _before_task_update(mapper, connection, target):
    target._prev_changes = _capture_changes(target, {"name": "Nom", "description": "Description"})


@event.listens_for(Task, 'after_update')
def _on_task_update(mapper, connection, target):
    changes = getattr(target, '_prev_changes', None) or []
    detail = {"changes": changes} if changes else None
    _log_recent(connection, 'task_updated', 'fa-solid fa-pen-to-square',
                f'{_event_label("event.task_updated")} : {target.name}', detail=detail)


# ── Roles ─────────────────────────────────────────────────────────
@event.listens_for(Role, 'after_insert')
def _on_role_insert(mapper, connection, target):
    detail = {"name": target.name, "mission": target.onboarding_plan or ""}
    _log_recent(connection, 'role_created', 'fa-solid fa-user-tie',
                f'{_event_label("event.role_created")} : {target.name}', target.entity_id, detail=detail)


@event.listens_for(Role, 'before_update')
def _before_role_update(mapper, connection, target):
    target._prev_changes = _capture_changes(target, {"name": "Nom", "onboarding_plan": "Mission"})


@event.listens_for(Role, 'after_update')
def _on_role_update(mapper, connection, target):
    changes = getattr(target, '_prev_changes', None) or []
    detail = {"changes": changes} if changes else None
    _log_recent(connection, 'role_updated', 'fa-solid fa-pen-to-square',
                f'{_event_label("event.role_updated")} : {target.name}', target.entity_id, detail=detail)


# ── Tools ──────────────────────────────────────────────────────────
@event.listens_for(Tool, 'after_insert')
def _on_tool_insert(mapper, connection, target):
    detail = {"name": target.name, "description": target.description or ""}
    _log_recent(connection, 'tool_created', 'fa-solid fa-toolbox',
                f'{_event_label("event.tool_created")} : {target.name}', target.entity_id, detail=detail)


@event.listens_for(Tool, 'before_update')
def _before_tool_update(mapper, connection, target):
    target._prev_changes = _capture_changes(target, {"name": "Nom", "description": "Description"})


@event.listens_for(Tool, 'after_update')
def _on_tool_update(mapper, connection, target):
    changes = getattr(target, '_prev_changes', None) or []
    detail = {"changes": changes} if changes else None
    _log_recent(connection, 'tool_updated', 'fa-solid fa-pen-to-square',
                f'{_event_label("event.tool_updated")} : {target.name}', target.entity_id, detail=detail)


# ── Suppressions ──────────────────────────────────────────────────
@event.listens_for(Activities, 'after_delete')
def _on_activity_delete(mapper, connection, target):
    detail = {"name": target.name, "description": target.description or ""}
    _log_recent(connection, 'activity_deleted', 'fa-solid fa-trash',
                f'{_event_label("event.activity_deleted")} : {target.name}', target.entity_id, detail=detail)


@event.listens_for(Task, 'after_delete')
def _on_task_delete(mapper, connection, target):
    detail = {"name": target.name}
    _log_recent(connection, 'task_deleted', 'fa-solid fa-trash',
                f'{_event_label("event.task_deleted")} : {target.name}', detail=detail)


@event.listens_for(Role, 'after_delete')
def _on_role_delete(mapper, connection, target):
    detail = {"name": target.name}
    _log_recent(connection, 'role_deleted', 'fa-solid fa-trash',
                f'{_event_label("event.role_deleted")} : {target.name}', target.entity_id, detail=detail)


@event.listens_for(Tool, 'after_delete')
def _on_tool_delete(mapper, connection, target):
    detail = {"name": target.name, "description": target.description or ""}
    _log_recent(connection, 'tool_deleted', 'fa-solid fa-trash',
                f'{_event_label("event.tool_deleted")} : {target.name}', target.entity_id, detail=detail)

class CrossCartoLiaison(db.Model):
    """Liaison officialisée entre une activité hachurée (extco) et son original."""
    __tablename__ = 'cross_carto_liaisons'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    extco_entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=False)
    extco_activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    origin_entity_id = db.Column(db.Integer, db.ForeignKey('entities.id'), nullable=False)
    origin_activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    display_label = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UsageEvent(db.Model):
    """Télémétrie OptiqPulse : une ligne par page vue (GET HTML) ou action
    (POST/PUT/PATCH/DELETE). Jamais affiché dans l'app — lu uniquement par le
    service externe OptiqPulse (pulse/) branché sur la base Neon de l'instance.
    Pas de FK sur users : la télémétrie survit à la suppression d'un compte."""
    __tablename__ = 'usage_events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ts = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    session_key = db.Column(db.String(32), nullable=True)
    kind = db.Column(db.String(10), nullable=False, default='view')  # view | action
    method = db.Column(db.String(8), nullable=False, default='GET')
    path = db.Column(db.String(300), nullable=False)
    endpoint = db.Column(db.String(120), nullable=True)
    status = db.Column(db.SmallInteger, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)


class UsageBeat(db.Model):
    """Battement de présence (~60 s, onglet visible) envoyé par pulse.js.
    Source du « connectés maintenant », des pics de fréquentation et du temps
    passé par page (delta entre battements consécutifs, plafonné côté Pulse)."""
    __tablename__ = 'usage_beats'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ts = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    session_key = db.Column(db.String(32), nullable=True)
    path = db.Column(db.String(300), nullable=True)


class AppSetting(db.Model):
    """Réglages d'instance modifiables à chaud (page Paramètres, section admin).
    Clés utilisées : 'openai_api_key'. Priorité sur les variables d'environnement."""
    __tablename__ = 'app_settings'

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, nullable=True)
