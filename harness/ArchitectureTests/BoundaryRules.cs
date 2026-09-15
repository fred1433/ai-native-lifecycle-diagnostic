using System.Reflection;
using NetArchTest.Rules;
using NUnit.Framework;

namespace ArchitectureTests;

/// <summary>
/// The boundaries an agent cannot see.
///
/// Every one of these rules is a sentence a senior engineer would say in a review and never
/// write down: the web layer does not talk to the database, the entities stay dumb, the ORM
/// stays behind the repository. An agent reads the code, finds a fifteen year old exception,
/// and reasonably concludes the rule does not exist. These tests are where the rule exists.
///
/// The dependency analysis is done on the compiled IL, so a call buried inside a method body
/// counts, not only a constructor parameter or a using directive.
/// </summary>
[TestFixture]
public class BoundaryRules
{
    private static Assembly Load(string name) =>
        Assembly.Load(new AssemblyName(name))
        ?? throw new InvalidOperationException($"assembly {name} is not in the output, the upstream build is incomplete");

    private static readonly Assembly Core = Load("Nop.Core");
    private static readonly Assembly Data = Load("Nop.Data");
    private static readonly Assembly Services = Load("Nop.Services");
    private static readonly Assembly WebFramework = Load("Nop.Web.Framework");
    private static readonly Assembly Web = Load("Nop.Web");

    [Test]
    [Description("A controller, a factory or a view model must ask a service, never the database.")]
    public void Presentation_must_not_reach_the_data_layer()
    {
        var result = Types.InAssembly(Web)
            .That().ResideInNamespaceStartingWith("Nop.Web")
            .And().DoNotResideInNamespaceStartingWith("Nop.Web.Infrastructure.Installation")
            .ShouldNot().HaveDependencyOn("Nop.Data")
            .GetResult();

        Check("presentation-must-not-reach-the-data-layer",
            "Types under Nop.Web that depend on Nop.Data.", result);
    }

    [Test]
    [Description("Services own the domain. A service that reaches into MVC has taken a decision that belongs one layer up.")]
    public void Services_must_not_depend_on_the_web_layer()
    {
        var result = Types.InAssembly(Services)
            .ShouldNot().HaveDependencyOnAny("Nop.Web", "Nop.Web.Framework")
            .GetResult();

        Check("services-must-not-depend-on-the-web-layer",
            "Types in Nop.Services that depend on the presentation assemblies.", result);
    }

    [Test]
    [Description("Entities are rows. The moment one of them can call a service, every load becomes a possible side effect.")]
    public void Domain_entities_stay_plain()
    {
        var result = Types.InAssembly(Core)
            .That().ResideInNamespaceStartingWith("Nop.Core.Domain")
            .ShouldNot().HaveDependencyOnAny("Nop.Services", "Nop.Data", "Nop.Web")
            .GetResult();

        Check("domain-entities-stay-plain",
            "Entity types under Nop.Core.Domain that depend on a layer above them.", result);
    }

    [Test]
    [Description("The ORM is an implementation detail of the data layer. Once it leaks, no query can be reviewed in one place.")]
    public void The_orm_stays_behind_the_repository()
    {
        var result = Types.InAssemblies(new[] { Services, WebFramework, Web })
            .ShouldNot().HaveDependencyOn("LinqToDB")
            .GetResult();

        Check("the-orm-stays-behind-the-repository",
            "Types outside Nop.Data that depend on the linq2db API.", result);
    }

    [Test]
    [Description("A concrete data provider is chosen once, at startup. Anywhere else it is a hidden coupling to one database engine.")]
    public void Concrete_data_providers_stay_in_the_data_layer()
    {
        var result = Types.InAssemblies(new[] { Core, Services, WebFramework, Web })
            .ShouldNot().HaveDependencyOnAny(
                "Nop.Data.DataProviders",
                "Microsoft.Data.SqlClient",
                "MySqlConnector",
                "Npgsql")
            .GetResult();

        Check("concrete-data-providers-stay-in-the-data-layer",
            "Types outside Nop.Data that depend on a concrete database driver.", result);
    }

    [Test]
    [Description("A rule nobody can point at is not a rule. This one proves the harness is actually looking at the platform.")]
    public void The_harness_is_measuring_the_real_platform()
    {
        Assert.Multiple(() =>
        {
            Assert.That(Types.InAssembly(Services).GetTypes().Count(), Is.GreaterThan(500),
                "Nop.Services should hold hundreds of types, the harness is pointed at the wrong build");
            Assert.That(Types.InAssembly(Data).GetTypes().Count(), Is.GreaterThan(50));
        });
    }

    private static void Check(string ruleId, string headline, TestResult result)
    {
        var failing = result.FailingTypeNames?.ToHashSet(StringComparer.Ordinal) ?? new HashSet<string>(StringComparer.Ordinal);

        if (Baseline.Writing)
        {
            Baseline.Write(ruleId, headline, failing);
            Assert.Pass($"baseline written for {ruleId}: {failing.Count} existing violations");
        }

        var baseline = Baseline.Load(ruleId);
        var added = failing.Except(baseline, StringComparer.Ordinal).OrderBy(n => n, StringComparer.Ordinal).ToList();
        var stale = baseline.Except(failing, StringComparer.Ordinal).OrderBy(n => n, StringComparer.Ordinal).ToList();

        Assert.Multiple(() =>
        {
            Assert.That(added, Is.Empty,
                $"{ruleId}: this change adds {added.Count} violation(s) of a boundary that holds everywhere else.");
            Assert.That(stale, Is.Empty,
                $"{ruleId}: {stale.Count} baseline entry(ies) no longer break the rule. Delete them from " +
                $"baseline/{ruleId}.txt, the list is a ratchet and only goes down.");
        });
    }
}
